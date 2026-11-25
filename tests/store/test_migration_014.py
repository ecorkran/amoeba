"""Migration 014 and what it adds: session versions, the machine's door version and
``machine_runs`` (slice 263, D5, D6, D13)."""

from __future__ import annotations

import dataclasses
import sqlite3
from collections.abc import Iterator
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from store_open import open_local_store

from amoeba.store.errors import StoreError
from amoeba.store.machine_runs import (
    all_machine_runs,
    delete_machine_runs,
    get_machine_runs,
    put_machine_runs,
)
from amoeba.store.machines import (
    act_as_local,
    hash_token,
    invite_machine,
    list_machines,
    machine_id_by_name,
    remove_machine,
    touch_machine,
)
from amoeba.store.migrations import (
    EXPECTED_SCHEMA_VERSION,
    migrate,
    read_schema_version,
)
from amoeba.store.models import Session
from amoeba.store.sessions import (
    live_member_ids,
    live_sessions,
    prune_stale_sessions,
    upsert_session,
)
from amoeba.store.store import Store
from amoeba.wire.times import DOOR_VERSION
from store.schema_13 import (
    MACHINE_NAME,
    MEMBER_ID,
    SESSION_COUNT,
    STAMP,
    build_schema_13_store,
)

STALE_SECONDS = 90
LATER = datetime(2026, 11, 24, 12, 0, tzinfo=UTC)
TOKEN = "a" * 64


def _session(session_id: str, door_version: int = DOOR_VERSION) -> Session:
    return Session(
        session_id=session_id,
        member_id=MEMBER_ID,
        client="claude-code",
        directory="/c",
        started_at=LATER,
        heartbeat_at=LATER,
        push_confirmed_at=LATER,
        client_version="9.9.9",
        door_version=door_version,
    )


@pytest.fixture
def schema_13(tmp_path: Path) -> Path:
    path = tmp_path / "old.sqlite3"
    build_schema_13_store(path)
    return path


@pytest.fixture
def connection(schema_13: Path) -> Iterator[sqlite3.Connection]:
    with closing(sqlite3.connect(schema_13, isolation_level=None)) as opened:
        opened.execute("PRAGMA foreign_keys=ON")
        yield opened


@pytest.fixture
def store(schema_13: Path) -> Iterator[Store]:
    with open_local_store(schema_13) as opened:
        yield opened


def _count(connection: sqlite3.Connection, table: str) -> int:
    return int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


def test_a_schema_13_store_migrates_with_its_rows(
    connection: sqlite3.Connection,
) -> None:
    tables = ("programs", "members", "machines", "sessions", "owners")
    before = {table: _count(connection, table) for table in tables}

    assert migrate(connection) == read_schema_version(connection)
    assert read_schema_version(connection) == EXPECTED_SCHEMA_VERSION

    assert {table: _count(connection, table) for table in tables} == before
    assert before["sessions"] == SESSION_COUNT
    assert _count(connection, "machine_runs") == 0


@pytest.mark.parametrize(
    ("client_version", "door_version"), [(None, 3), ("0.3.0", None), (None, None)]
)
def test_a_session_insert_without_its_versions_is_refused(
    connection: sqlite3.Connection, client_version: str | None, door_version: int | None
) -> None:
    migrate(connection)

    with pytest.raises(sqlite3.IntegrityError, match="client_version"):
        connection.execute(
            "INSERT INTO sessions (session_id, member_id, client, directory, "
            "started_at, heartbeat_at, owner_id, machine_id, client_version, "
            "door_version) VALUES ('new', ?, 'c', '/c', ?, ?, "
            "(SELECT owner_id FROM owners), (SELECT machine_id FROM machines), ?, ?)",
            (MEMBER_ID, STAMP, STAMP, client_version, door_version),
        )


def test_a_row_from_before_the_migration_is_never_live_and_the_next_prune_deletes_it(
    connection: sqlite3.Connection, schema_13: Path
) -> None:
    migrate(connection)
    connection.close()
    # The old rows' heartbeat is fresh as of the reads below; only the missing door
    # version keeps them out.
    now = datetime(2026, 11, 1, tzinfo=UTC)

    with open_local_store(schema_13) as store:
        with store.read() as transaction:
            assert live_sessions(transaction, now, STALE_SECONDS) == ()
            assert live_member_ids(transaction, now, STALE_SECONDS, DOOR_VERSION) == (
                frozenset()
            )
        with store.write() as transaction:
            prune_stale_sessions(transaction, now, STALE_SECONDS)
        with store.read() as transaction:
            rows = transaction.execute("SELECT COUNT(*) FROM sessions").fetchone()
    assert rows[0] == 0


def test_machine_runs_is_one_row_per_machine_replaced_by_each_put(
    store: Store,
) -> None:
    later = LATER + timedelta(minutes=1)
    with store.write() as transaction:
        put_machine_runs(transaction, '{"runs": []}', LATER)
        put_machine_runs(transaction, '{"runs": [1]}', later)
    with store.read() as transaction:
        machine_id = machine_id_by_name(transaction, MACHINE_NAME)
        assert machine_id is not None
        stored = get_machine_runs(transaction, machine_id)
        everything = all_machine_runs(transaction)
        count = transaction.execute("SELECT COUNT(*) FROM machine_runs").fetchone()[0]

    assert count == 1
    assert stored is not None
    assert (stored.document, stored.reported_at, stored.machine) == (
        '{"runs": [1]}',
        later,
        MACHINE_NAME,
    )
    assert everything == (stored,)


def test_remove_machine_deletes_its_stored_runs_and_no_other(store: Store) -> None:
    with store.write() as transaction:
        invite_machine(transaction, "beta", hash_token(TOKEN), LATER)
        beta = machine_id_by_name(transaction, "beta")
        local = machine_id_by_name(transaction, MACHINE_NAME)
    assert beta is not None
    assert local is not None
    with store.write() as transaction:
        put_machine_runs(transaction, "{}", LATER)
    store.act_as(dataclasses.replace(act_as_local(store), machine_id=beta))
    with store.write() as transaction:
        put_machine_runs(transaction, "{}", LATER)
        assert remove_machine(transaction, "beta") is True
        assert get_machine_runs(transaction, beta) is None
        assert get_machine_runs(transaction, local) is not None
        delete_machine_runs(transaction, local)
        assert get_machine_runs(transaction, local) is None


def test_a_session_on_another_door_version_is_listed_but_does_not_hold_off_a_wake(
    store: Store,
) -> None:
    with store.write() as transaction:
        upsert_session(transaction, _session("behind", DOOR_VERSION - 1))
    with store.read() as transaction:
        listed = live_sessions(transaction, LATER, STALE_SECONDS)
        waking = live_member_ids(transaction, LATER, STALE_SECONDS, DOOR_VERSION)
        waking_older = live_member_ids(
            transaction, LATER, STALE_SECONDS, DOOR_VERSION - 1
        )

    assert [session.session_id for session in listed] == ["behind"]
    assert waking == frozenset()
    assert waking_older == frozenset({MEMBER_ID})


def test_a_current_push_confirmed_session_is_listed_and_holds_off_a_wake(
    store: Store,
) -> None:
    with store.write() as transaction:
        upsert_session(transaction, _session("current"))
    with store.read() as transaction:
        listed = live_sessions(transaction, LATER, STALE_SECONDS)
        waking = live_member_ids(transaction, LATER, STALE_SECONDS, DOOR_VERSION)

    assert [session.session_id for session in listed] == ["current"]
    assert waking == frozenset({MEMBER_ID})


def test_another_machines_session_id_is_not_refreshed(store: Store) -> None:
    with store.write() as transaction:
        invite_machine(transaction, "beta", hash_token(TOKEN), LATER)
        upsert_session(transaction, _session("shared"))
    with store.write() as transaction:
        beta = machine_id_by_name(transaction, "beta")
    assert beta is not None
    store.act_as(
        dataclasses.replace(act_as_local(store), machine_id=beta)
    )  # beta tries to write local's session id
    before = _row(store)
    with pytest.raises(StoreError, match="another machine"), store.write() as tx:
        upsert_session(
            tx,
            dataclasses.replace(
                _session("shared"), heartbeat_at=LATER + timedelta(hours=1)
            ),
        )

    assert _row(store) == before


def _row(store: Store) -> tuple[object, ...]:
    with store.read() as transaction:
        return tuple(
            transaction.execute(
                "SELECT * FROM sessions WHERE session_id = 'shared'"
            ).fetchone()
        )


def test_touch_machine_sets_both_versions_unless_told_to_keep_them(
    store: Store,
) -> None:
    digest = hash_token(TOKEN)
    with store.write() as transaction:
        invite_machine(transaction, "beta", digest, LATER)
        touch_machine(transaction, digest, LATER, "0.2.9", 3)
        touch_machine(
            transaction,
            digest,
            LATER + timedelta(seconds=5),
            "0.2.1",
            2,
            keep_versions=True,
        )
        kept = [m for m in list_machines(transaction) if m.name == "beta"][0]
        touch_machine(transaction, digest, LATER, "0.3.0", None)
        unparsed = [m for m in list_machines(transaction) if m.name == "beta"][0]

    assert (kept.client_version, kept.door_version) == ("0.2.9", 3)
    assert kept.last_called_at == LATER + timedelta(seconds=5)
    assert (unparsed.client_version, unparsed.door_version) == ("0.3.0", 3)
