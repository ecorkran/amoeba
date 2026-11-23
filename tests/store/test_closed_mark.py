"""The closed mark: a set-aside store takes no more writes (slice 260, D4)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from store_open import open_local_store

from amoeba.store.errors import LocalStoreClosedError
from amoeba.store.machines import write_closed_mark
from amoeba.store.store import Store, Transaction

HUB = "hub.example:8443"
NOW = datetime(2026, 11, 21, 9, 0, tzinfo=UTC)


def _add_program(transaction: Transaction, name: str) -> None:
    transaction.execute(
        "INSERT INTO programs (program_id, registered_at, updated_at, owner_id) "
        "VALUES (?, 't', 't', ?)",
        (name, transaction.acting("programs").owner_id),
    )


def _program_count(store: Store) -> int:
    with store.read() as transaction:
        return int(transaction.execute("SELECT COUNT(*) FROM programs").fetchone()[0])


@pytest.fixture
def path(tmp_path: Path) -> Path:
    return tmp_path / "amoeba.sqlite3"


def test_a_write_after_the_mark_names_the_hub_and_writes_nothing(path: Path) -> None:
    with open_local_store(path) as store:
        with store.write() as transaction:
            write_closed_mark(transaction, HUB, NOW)

        with pytest.raises(LocalStoreClosedError, match=HUB), store.write() as tx:
            _add_program(tx, "a")

        assert _program_count(store) == 0


def test_the_message_names_both_ways_out(path: Path) -> None:
    with open_local_store(path) as store:
        with store.write() as transaction:
            write_closed_mark(transaction, HUB, NOW)

        with pytest.raises(LocalStoreClosedError) as raised, store.write():
            pass

    assert "amoeba leave" in str(raised.value)
    assert "amoeba join" in str(raised.value)


def test_a_call_scope_is_refused_too(path: Path) -> None:
    with open_local_store(path) as store:
        with store.write() as transaction:
            write_closed_mark(transaction, HUB, NOW)

        with pytest.raises(LocalStoreClosedError), store.call_scope():
            pass


def test_reads_still_work(path: Path) -> None:
    with open_local_store(path) as store:
        with store.write() as transaction:
            _add_program(transaction, "a")
            write_closed_mark(transaction, HUB, NOW)

        assert _program_count(store) == 1


def test_a_second_connection_opened_earlier_fails_its_next_write(path: Path) -> None:
    with open_local_store(path) as early, open_local_store(path) as late:
        with early.write() as transaction:
            _add_program(transaction, "before")

        with late.write() as transaction:
            write_closed_mark(transaction, HUB, NOW)

        with pytest.raises(LocalStoreClosedError, match=HUB), early.write() as tx:
            _add_program(tx, "after")

        assert _program_count(early) == 1


def test_with_no_mark_writes_are_unchanged(path: Path) -> None:
    with open_local_store(path) as store:
        with store.write() as transaction:
            _add_program(transaction, "a")

        assert _program_count(store) == 1


def test_writing_the_mark_again_replaces_it(path: Path) -> None:
    with open_local_store(path) as store:
        with store.write() as transaction:
            write_closed_mark(transaction, HUB, NOW)
        with pytest.raises(LocalStoreClosedError), store.write():
            pass
        with store.read() as transaction:
            marks = transaction.execute(
                "SELECT hub_address FROM closed_mark"
            ).fetchall()

    assert [row[0] for row in marks] == [HUB]
