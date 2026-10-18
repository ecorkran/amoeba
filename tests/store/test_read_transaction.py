"""``read_transaction`` and ``change_head``: several reads against one snapshot."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from amoeba.store import NodeKind, Store

PROJECT = "demo"


class _ReadFailedError(Exception):
    """Raised inside a read transaction by a test."""


def _create_node(store: Store) -> None:
    store.create_node(project_id=PROJECT, kind=NodeKind.SLICE, title="n")


@pytest.fixture
def reader(store: Store, store_file: Path) -> Iterator[Store]:
    """A read-only handle on the store the ``store`` fixture writes."""
    with Store.open_read_only(store_file) as opened:
        yield opened


def test_change_head_is_zero_on_an_empty_feed(store: Store) -> None:
    assert store.change_head(PROJECT) == 0


def test_change_head_is_the_last_seq_after_commits(store: Store) -> None:
    _create_node(store)
    _create_node(store)

    last_seq = store.changes(PROJECT, limit=100)[-1].seq

    assert store.change_head(PROJECT) == last_seq


def test_reads_inside_a_transaction_share_one_snapshot(
    store: Store, reader: Store
) -> None:
    _create_node(store)
    head_before = reader.change_head(PROJECT)

    with reader.read_transaction():
        first = reader.change_head(PROJECT)
        _create_node(store)  # committed through the separate read-write handle
        second = reader.change_head(PROJECT)

    assert first == second == head_before
    assert reader.change_head(PROJECT) > head_before


def test_the_handle_is_usable_after_a_read_raises(store: Store, reader: Store) -> None:
    with pytest.raises(_ReadFailedError), reader.read_transaction():
        reader.change_head(PROJECT)
        raise _ReadFailedError

    _create_node(store)

    # A transaction left open would refuse this BEGIN, and pin the old snapshot.
    with reader.read_transaction():
        assert reader.change_head(PROJECT) == store.change_head(PROJECT)
