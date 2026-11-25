"""Machines, tokens and their removal (slice 260, D3, D8, D13)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from store_open import open_local_store

from amoeba.store.call_results import keep
from amoeba.store.errors import StoreIntegrityError
from amoeba.store.machines import (
    hash_token,
    invite_machine,
    list_machines,
    machine_for_token,
    remove_machine,
    the_owner,
    touch_machine,
)
from amoeba.store.models import Session
from amoeba.store.sessions import upsert_session
from amoeba.store.store import Store
from amoeba.wire.times import DOOR_VERSION

NOW = datetime(2026, 11, 21, 10, 0, tzinfo=UTC)
LATER = NOW + timedelta(minutes=5)
ALPHA = hash_token("alpha-token-one")
BETA = hash_token("beta-token-one")


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    with Store.open(tmp_path / "amoeba.sqlite3") as opened:
        yield opened


def test_a_token_hash_is_the_sha256_hex_and_never_the_token() -> None:
    assert len(ALPHA) == 64
    assert "alpha" not in ALPHA
    assert hash_token("alpha-token-one") == ALPHA


def test_a_new_invite_makes_the_machine_with_the_owner(store: Store) -> None:
    with store.write() as tx:
        assert invite_machine(tx, "alpha", ALPHA, NOW) is True
        owner = the_owner(tx)
        row = tx.execute("SELECT name, owner_id, token_hash FROM machines").fetchone()

    assert tuple(row) == ("alpha", owner, ALPHA)


def test_a_reinvite_replaces_the_hash_so_the_old_one_finds_nothing(
    store: Store,
) -> None:
    with store.write() as tx:
        invite_machine(tx, "alpha", ALPHA, NOW)
        assert invite_machine(tx, "alpha", BETA, LATER) is False
        old = machine_for_token(tx, ALPHA)
        new = machine_for_token(tx, BETA)
        count = tx.execute("SELECT COUNT(*) FROM machines").fetchone()[0]

    assert old is None
    assert new is not None
    assert count == 1


def test_two_machines_cannot_share_a_name(store: Store) -> None:
    with store.write() as tx:
        invite_machine(tx, "alpha", ALPHA, NOW)
        with pytest.raises(StoreIntegrityError):
            tx.execute(
                "INSERT INTO machines (name, owner_id, token_hash, created_at) "
                "VALUES ('alpha', ?, 'other', 't')",
                (the_owner(tx),),
            )


def test_touch_sets_both_fields_and_returns_the_machine(store: Store) -> None:
    with store.write() as tx:
        invite_machine(tx, "alpha", ALPHA, NOW)
        machine = touch_machine(tx, ALPHA, LATER, "0.2.3", None)
        row = tx.execute(
            "SELECT last_called_at, client_version FROM machines"
        ).fetchone()
        known = machine_for_token(tx, ALPHA)

    assert machine is not None
    assert machine == known
    assert tuple(row) == (LATER.isoformat(), "0.2.3")


def test_touching_an_unknown_hash_returns_none(store: Store) -> None:
    with store.write() as tx:
        assert touch_machine(tx, ALPHA, NOW, "0.2.3", None) is None


def test_list_machines_shows_a_machine_with_no_token(store: Store) -> None:
    with store.write() as tx:
        invite_machine(tx, "beta", BETA, NOW)
        invite_machine(tx, "alpha", ALPHA, NOW)
        touch_machine(tx, ALPHA, LATER, "0.2.3", None)
        tx.execute(
            "INSERT INTO machines (name, owner_id, token_hash, created_at) "
            "VALUES ('local', ?, NULL, 't')",
            (the_owner(tx),),
        )
        rows = list_machines(tx)

    assert [(r.name, r.has_token, r.client_version) for r in rows] == [
        ("alpha", True, "0.2.3"),
        ("beta", True, None),
        ("local", False, None),
    ]
    assert rows[0].last_called_at == LATER
    assert rows[1].last_called_at is None


def _seed_member(store: Store) -> None:
    with store.write() as tx:
        owner = the_owner(tx)
        tx.execute(
            "INSERT INTO programs (program_id, registered_at, updated_at, owner_id) "
            "VALUES ('demo', 't', 't', ?)",
            (owner,),
        )
        tx.execute(
            "INSERT INTO members (project_id, program_id, rules_paths, "
            "authorize_allow, authorize_deny, registered_at, updated_at, name, "
            "owner_id) "
            "VALUES ('m1', 'demo', '[]', '[]', '[]', 't', 't', 'm1', ?)",
            (owner,),
        )


def test_remove_deletes_its_sessions_and_results_and_no_one_elses(
    tmp_path: Path,
) -> None:
    with open_local_store(tmp_path / "amoeba.sqlite3") as store:
        _seed_member(store)
        with store.write() as tx:
            invite_machine(tx, "alpha", ALPHA, NOW)
            invite_machine(tx, "beta", BETA, NOW)
        for name, token in (("alpha", ALPHA), ("beta", BETA)):
            with store.read() as tx:
                machine = machine_for_token(tx, token)
            assert machine is not None
            store.act_as(machine)
            with store.write() as tx:
                upsert_session(
                    tx,
                    Session(
                        f"s-{name}",
                        "m1",
                        "claude",
                        "/c",
                        NOW,
                        NOW,
                        None,
                        "9.9.9",
                        DOOR_VERSION,
                    ),
                )
                keep(tx, machine.machine_id, "call-1", "standing", "h", "{}", NOW)

        with store.write() as tx:
            assert remove_machine(tx, "alpha") is True

        with store.read() as tx:
            sessions = [r[0] for r in tx.execute("SELECT session_id FROM sessions")]
            kept = tx.execute("SELECT COUNT(*) FROM call_results").fetchone()[0]
            names = [r.name for r in list_machines(tx)]

    assert sessions == ["s-beta"]
    assert kept == 1
    assert names == ["beta", "local"]


def test_removing_an_unknown_machine_returns_false(store: Store) -> None:
    with store.write() as tx:
        assert remove_machine(tx, "nobody") is False
