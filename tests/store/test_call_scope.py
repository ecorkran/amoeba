"""``Store.call_scope``: one transaction whose inner blocks are savepoints (D8)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from store_open import open_local_store

from amoeba.store.store import Store, Transaction


class Boom(Exception):
    """An error of the test's own."""


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    with open_local_store(tmp_path / "amoeba.sqlite3") as opened:
        yield opened


def _add_program(transaction: Transaction, name: str) -> None:
    owner = transaction.acting("programs").owner_id
    transaction.execute(
        "INSERT INTO programs (program_id, registered_at, updated_at, owner_id) "
        "VALUES (?, 't', 't', ?)",
        (name, owner),
    )


def _programs(store: Store) -> list[str]:
    with store.read() as transaction:
        rows = transaction.execute("SELECT program_id FROM programs ORDER BY 1")
        return [row[0] for row in rows]


def test_a_scope_commits_what_it_wrote(store: Store) -> None:
    with store.call_scope() as scope:
        _add_program(scope, "a")

    assert _programs(store) == ["a"]


def test_a_nested_write_that_raises_keeps_the_scope_and_drops_itself(
    store: Store,
) -> None:
    with store.call_scope() as scope:
        _add_program(scope, "outer")
        with pytest.raises(Boom), store.write() as inner:
            _add_program(inner, "nested")
            raise Boom
        with store.write() as inner:
            _add_program(inner, "after")

    assert _programs(store) == ["after", "outer"]


def test_two_nested_levels_roll_back_to_the_right_point(store: Store) -> None:
    with store.call_scope(), store.write() as middle:
        _add_program(middle, "middle")
        with store.write() as inner:
            _add_program(inner, "kept-inner")
        with pytest.raises(Boom), store.write() as inner:
            _add_program(inner, "dropped-inner")
            raise Boom

    assert _programs(store) == ["kept-inner", "middle"]


def test_an_exception_out_of_the_scope_leaves_nothing(store: Store) -> None:
    with pytest.raises(Boom), store.call_scope() as scope:
        _add_program(scope, "a")
        with store.write() as inner:
            _add_program(inner, "b")
        raise Boom

    assert _programs(store) == []


def test_a_nested_call_scope_is_a_programming_error(store: Store) -> None:
    with store.call_scope(), pytest.raises(RuntimeError, match="call_scope"):
        with store.call_scope():
            pass


def test_the_scope_ends_after_an_exception_so_a_later_one_can_start(
    store: Store,
) -> None:
    with pytest.raises(Boom), store.call_scope():
        raise Boom

    with store.call_scope() as scope:
        _add_program(scope, "a")

    assert _programs(store) == ["a"]


def test_a_read_in_a_scope_sees_the_scopes_writes(store: Store) -> None:
    with store.call_scope() as scope:
        _add_program(scope, "a")
        with store.read() as reading:
            seen = reading.execute("SELECT program_id FROM programs").fetchall()

    assert [row[0] for row in seen] == ["a"]


def test_outside_a_scope_write_commits_per_block(store: Store) -> None:
    with store.write() as transaction:
        _add_program(transaction, "a")
    with pytest.raises(Boom), store.write() as transaction:
        _add_program(transaction, "b")
        raise Boom

    assert _programs(store) == ["a"]
