"""record_check and record_progress: every check, the retry rule, the round trip."""

from __future__ import annotations

import dataclasses
import logging

import pytest
from evidence_harness import CHECK_PROVENANCE as PROVENANCE
from evidence_harness import PROJECT, check_input, seed_node

from amoeba.store import (
    CheckOutcome,
    CheckStanding,
    NodeNotFoundError,
    ProgressInput,
    ProgressKind,
    Store,
    StoreIntegrityError,
    sql_checks,
)


def test_a_check_round_trips_with_examined_and_baseline(store: Store) -> None:
    node = seed_node(store)
    given = check_input(
        "c1", node, examined={"files": ["a.py", "b.py"]}, baseline_ref="abc123"
    )
    record = store.record_check(given, project_id=PROJECT)

    assert record.project_id == PROJECT
    assert record.examined == {"files": ["a.py", "b.py"]}
    assert record.baseline_ref == "abc123"
    assert record.provenance == PROVENANCE
    assert record.standing is CheckStanding.PASSED
    assert store.check("c1") == record


def test_an_unknown_id_returns_none(store: Store) -> None:
    assert store.check("nope") is None


def test_checks_are_in_arrival_order_and_filter_by_node(store: Store) -> None:
    first, second = seed_node(store), seed_node(store)
    store.record_check(check_input("c1", first), project_id=PROJECT)
    store.record_check(check_input("c2", second), project_id=PROJECT)
    store.record_check(check_input("c3", first), project_id=PROJECT)

    assert [c.id for c in store.checks(PROJECT)] == ["c1", "c2", "c3"]
    assert [c.id for c in store.checks(PROJECT, node_id=first)] == ["c1", "c3"]
    assert [c.recorded_seq for c in store.checks(PROJECT)] == sorted(
        c.recorded_seq for c in store.checks(PROJECT)
    )


def test_a_missing_node_raises_and_writes_nothing(store: Store) -> None:
    with pytest.raises(NodeNotFoundError, match="ghost"):
        store.record_check(check_input("c1", "ghost"), project_id=PROJECT)
    assert store.checks(PROJECT) == []


def test_a_node_in_another_project_raises(store: Store) -> None:
    node = seed_node(store, "other")
    with pytest.raises(NodeNotFoundError):
        store.record_check(check_input("c1", node), project_id=PROJECT)


def test_a_negative_examined_count_raises(store: Store) -> None:
    node = seed_node(store)
    with pytest.raises(ValueError, match="-1"):
        store.record_check(
            check_input("c1", node, examined_count=-1), project_id=PROJECT
        )
    assert store.checks(PROJECT) == []


def test_an_empty_upstream_version_raises(store: Store) -> None:
    node = seed_node(store)
    blank = dataclasses.replace(PROVENANCE, upstream_version=" ")
    with pytest.raises(ValueError, match="upstream_version"):
        store.record_check(
            check_input("c1", node, provenance=blank), project_id=PROJECT
        )


def test_a_null_and_a_zero_count_are_recorded_and_stand_apart(store: Store) -> None:
    node = seed_node(store)
    unreported = store.record_check(
        check_input("c1", node, examined_count=None), project_id=PROJECT
    )
    nothing = store.record_check(
        check_input("c2", node, examined_count=0), project_id=PROJECT
    )
    assert unreported.examined_count is None
    assert unreported.standing is CheckStanding.UNATTESTED
    assert nothing.standing is CheckStanding.VACUOUS


def test_retrying_returns_the_existing_record_and_writes_no_second_row(
    store: Store, caplog: pytest.LogCaptureFixture
) -> None:
    node = seed_node(store)
    first = store.record_check(check_input("c1", node), project_id=PROJECT)
    with caplog.at_level(logging.WARNING):
        again = store.record_check(check_input("c1", node), project_id=PROJECT)
    assert again == first
    assert len(store.checks(PROJECT)) == 1
    assert caplog.records == []


def test_a_differing_retry_warns_and_keeps_the_first(
    store: Store, caplog: pytest.LogCaptureFixture
) -> None:
    node = seed_node(store)
    first = store.record_check(check_input("c1", node), project_id=PROJECT)
    with caplog.at_level(logging.WARNING):
        again = store.record_check(
            check_input("c1", node, outcome=CheckOutcome.FAILED), project_id=PROJECT
        )
    assert again == first
    assert again.outcome is CheckOutcome.PASSED
    assert [r.levelno for r in caplog.records] == [logging.WARNING]
    assert len(store.checks(PROJECT)) == 1


def _progress(progress_id: str, node_id: str) -> ProgressInput:
    return ProgressInput(
        id=progress_id,
        node_id=node_id,
        progress_kind=ProgressKind.DEVLOG,
        content={"entry": "did a thing", "items": [1, 2]},
        provenance=PROVENANCE,
    )


def _select(store: Store, statement: str) -> list[tuple[object, ...]]:
    connection = store._connection  # pyright: ignore[reportPrivateUsage]
    return connection.execute(statement).fetchall()


def _progress_rows(store: Store) -> list[tuple[object, ...]]:
    return _select(
        store,
        f"SELECT {sql_checks.COL_PROGRESS_ID}, {sql_checks.COL_PROGRESS_KIND}, "
        f"{sql_checks.COL_PROGRESS_CONTENT} FROM {sql_checks.TABLE_PROGRESS_RECORDS}",
    )


def test_record_progress_writes_a_row_whose_content_reads_back_unchanged(
    store: Store,
) -> None:
    node = seed_node(store)
    assert store.record_progress(_progress("p1", node), project_id=PROJECT) is None
    [(row_id, kind, content)] = _progress_rows(store)
    assert (row_id, kind) == ("p1", "devlog")
    assert content == '{"entry": "did a thing", "items": [1, 2]}'


def test_a_repeated_progress_id_raises(store: Store) -> None:
    node = seed_node(store)
    store.record_progress(_progress("p1", node), project_id=PROJECT)
    with pytest.raises(StoreIntegrityError):
        store.record_progress(_progress("p1", node), project_id=PROJECT)
    assert len(_progress_rows(store)) == 1


def test_a_progress_record_for_a_missing_node_raises(store: Store) -> None:
    with pytest.raises(StoreIntegrityError):
        store.record_progress(_progress("p1", "ghost"), project_id=PROJECT)
    assert _progress_rows(store) == []


def test_progress_writes_no_feed_change(store: Store) -> None:
    node = seed_node(store)
    count = "SELECT COUNT(*) FROM changes"
    before = _select(store, count)
    store.record_progress(_progress("p1", node), project_id=PROJECT)
    assert _select(store, count) == before
