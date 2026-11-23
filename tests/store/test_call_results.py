"""Kept results of writing calls (slice 260, D9)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from amoeba.store import sql_call_results
from amoeba.store.call_results import KeptResult, delete_expired, find_kept, keep
from amoeba.store.machines import hash_token, invite_machine
from amoeba.store.store import Store, Transaction

NOW = datetime(2026, 11, 21, 10, 0, tzinfo=UTC)
LIFETIME = 600.0


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    with Store.open(tmp_path / "amoeba.sqlite3") as opened:
        with opened.write() as tx:
            invite_machine(tx, "alpha", hash_token("a-token"), NOW)
            invite_machine(tx, "beta", hash_token("b-token"), NOW)
        yield opened


def _machine_ids(tx: Transaction) -> tuple[int, int]:
    rows = tx.execute("SELECT machine_id FROM machines ORDER BY name").fetchall()
    return int(rows[0][0]), int(rows[1][0])


def test_keep_then_find(store: Store) -> None:
    with store.write() as tx:
        alpha, _ = _machine_ids(tx)
        keep(tx, alpha, "c1", "standing", "hash-1", '{"outcome": "done"}', NOW)
        found = find_kept(tx, alpha, "c1")

    assert found == KeptResult("standing", "hash-1", '{"outcome": "done"}')


def test_an_unknown_call_finds_nothing(store: Store) -> None:
    with store.read() as tx:
        alpha, _ = _machine_ids(tx)
        assert find_kept(tx, alpha, "nope") is None


def test_the_same_call_id_under_two_machines_is_two_rows(store: Store) -> None:
    with store.write() as tx:
        alpha, beta = _machine_ids(tx)
        keep(tx, alpha, "c1", "standing", "h1", "first", NOW)
        keep(tx, beta, "c1", "withdraw", "h2", "second", NOW)
        first = find_kept(tx, alpha, "c1")
        second = find_kept(tx, beta, "c1")

    assert first is not None and first.reply == "first"
    assert second is not None and second.reply == "second"


def test_delete_expired_removes_only_rows_older_than_the_lifetime(
    store: Store,
) -> None:
    with store.write() as tx:
        alpha, _ = _machine_ids(tx)
        keep(tx, alpha, "old", "standing", "h", "r", NOW - timedelta(seconds=601))
        keep(tx, alpha, "edge", "standing", "h", "r", NOW - timedelta(seconds=600))
        keep(tx, alpha, "new", "standing", "h", "r", NOW - timedelta(seconds=10))
        delete_expired(tx, NOW, LIFETIME)
        left = [r[0] for r in tx.execute("SELECT call_id FROM call_results ORDER BY 1")]

    assert left == ["edge", "new"]


def test_the_expiry_delete_uses_the_time_index(store: Store) -> None:
    with store.read() as tx:
        plan = tx.execute(
            f"EXPLAIN QUERY PLAN {sql_call_results.DELETE_EXPIRED}", ("t",)
        ).fetchall()

    assert any("call_results_recorded_at" in str(row[3]) for row in plan)
