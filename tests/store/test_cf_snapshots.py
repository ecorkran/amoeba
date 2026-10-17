"""Context Forge links and snapshots: the store operations and the feed trigger."""

from __future__ import annotations

import dataclasses

import pytest
from cf_harness import OBSERVED_AT, VERSION_LABEL, failure, observed
from feed_harness import raw_changes

from amoeba.store import (
    CFSnapshotOutcome,
    ChangeKind,
    Store,
    sql_cf,
)
from amoeba.store.mapping_cf import map_snapshot
from amoeba.store.models import UnknownVocabularyValueError

PROJECT = "demo"
CF_ID = "project_1_abc"
FAILURES = [
    outcome
    for outcome in CFSnapshotOutcome
    if outcome is not CFSnapshotOutcome.OBSERVED
]


def _cf_changes(store: Store, project_id: str = PROJECT):
    return [
        change
        for change in raw_changes(store, project_id)
        if change.kind is ChangeKind.CF_PROJECT_CHANGED
    ]


def test_an_observed_snapshot_reads_back_whole(store: Store) -> None:
    recorded = store.record_cf_snapshot(observed(PROJECT, CF_ID))
    assert recorded.id == 1
    assert recorded.outcome is CFSnapshotOutcome.OBSERVED
    assert recorded.state == {"project": {"name": "demo"}, "worktrees": {}}
    assert recorded.changed == [{"worktree_id": None, "field": "name", "to": "demo"}]
    assert recorded.detail is None
    assert recorded.cf_updated_at == "2026-10-16T12:00:00.000Z"
    assert recorded.cf_version_label == VERSION_LABEL
    assert recorded.observed_at == OBSERVED_AT
    assert store.cf_snapshots(PROJECT) == [recorded]


@pytest.mark.parametrize("outcome", FAILURES)
def test_each_failure_outcome_reads_back_with_its_detail(
    store: Store, outcome: CFSnapshotOutcome
) -> None:
    recorded = store.record_cf_snapshot(failure(PROJECT, CF_ID, outcome, "why"))
    assert recorded.outcome is outcome
    assert (recorded.state, recorded.changed, recorded.detail) == (None, None, "why")


def test_every_insert_adds_exactly_one_change_with_the_documented_payload(
    store: Store,
) -> None:
    first = store.record_cf_snapshot(observed(PROJECT, CF_ID))
    bad = store.record_cf_snapshot(
        failure(PROJECT, CF_ID, CFSnapshotOutcome.UNRECOGNIZED)
    )
    changes = _cf_changes(store)
    assert [change.subject_id for change in changes] == [str(first.id), str(bad.id)]
    assert changes[0].payload == {
        "cf_project_id": CF_ID,
        "outcome": "observed",
        "changed": first.changed,
    }
    assert changes[1].payload == {
        "cf_project_id": CF_ID,
        "outcome": "unrecognized",
        "changed": None,
    }
    assert all(change.node_id is None for change in changes)
    assert all(change.recorded_at == OBSERVED_AT for change in changes)


def test_a_recovery_row_with_no_changes_still_emits_a_change(store: Store) -> None:
    store.record_cf_snapshot(observed(PROJECT, CF_ID, changed=[]))
    (change,) = _cf_changes(store)
    assert change.payload["changed"] == []


def test_latest_returns_the_latest_row_and_the_latest_observed_row(
    store: Store,
) -> None:
    assert store.latest_cf_snapshots(PROJECT, CF_ID) == (None, None)
    first = store.record_cf_snapshot(observed(PROJECT, CF_ID))
    assert store.latest_cf_snapshots(PROJECT, CF_ID) == (first, first)
    bad = store.record_cf_snapshot(
        failure(PROJECT, CF_ID, CFSnapshotOutcome.UNREADABLE)
    )
    assert store.latest_cf_snapshots(PROJECT, CF_ID) == (bad, first)


def test_latest_is_none_for_observed_when_only_failures_exist(store: Store) -> None:
    bad = store.record_cf_snapshot(failure(PROJECT, CF_ID, CFSnapshotOutcome.MISSING))
    assert store.latest_cf_snapshots(PROJECT, CF_ID) == (bad, None)


def test_latest_is_per_project_and_per_link(store: Store) -> None:
    store.record_cf_snapshot(observed(PROJECT, CF_ID))
    assert store.latest_cf_snapshots(PROJECT, "other") == (None, None)
    assert store.latest_cf_snapshots("elsewhere", CF_ID) == (None, None)


def test_snapshots_are_in_id_order_and_per_project(store: Store) -> None:
    ids = [
        store.record_cf_snapshot(observed(PROJECT, CF_ID)).id,
        store.record_cf_snapshot(observed("elsewhere", CF_ID)).id,
        store.record_cf_snapshot(observed(PROJECT, "second")).id,
    ]
    assert [s.id for s in store.cf_snapshots(PROJECT)] == [ids[0], ids[2]]
    assert [s.id for s in store.cf_snapshots("elsewhere")] == [ids[1]]


@pytest.mark.parametrize(
    "bad",
    [
        {"state": None},
        {"changed": None},
        {"detail": "not allowed when observed"},
    ],
)
def test_an_inconsistent_observed_snapshot_is_refused(
    store: Store, bad: dict[str, object]
) -> None:
    with pytest.raises(ValueError):
        store.record_cf_snapshot(observed(PROJECT, CF_ID, **bad))
    assert store.cf_snapshots(PROJECT) == []


@pytest.mark.parametrize(
    "bad",
    [{"state": {}}, {"changed": []}, {"detail": None}],
)
def test_an_inconsistent_failure_snapshot_is_refused(
    store: Store, bad: dict[str, object]
) -> None:
    snapshot = dataclasses.replace(
        failure(PROJECT, CF_ID, CFSnapshotOutcome.MISSING),
        **bad,  # pyright: ignore[reportArgumentType]
    )
    with pytest.raises(ValueError):
        store.record_cf_snapshot(snapshot)
    assert store.cf_snapshots(PROJECT) == []


def test_a_stored_unknown_outcome_raises_rather_than_defaulting() -> None:
    row = (1, PROJECT, CF_ID, "maybe", None, None, "d", None, VERSION_LABEL)
    with pytest.raises(UnknownVocabularyValueError, match="maybe"):
        map_snapshot(row + (OBSERVED_AT.isoformat(),))


def test_a_row_of_the_wrong_width_raises() -> None:
    with pytest.raises(UnknownVocabularyValueError, match="columns"):
        map_snapshot((1, PROJECT))


def test_the_store_and_column_constants_agree() -> None:
    assert len(sql_cf.SNAPSHOT_INSERT_COLUMNS) == len(sql_cf.SNAPSHOT_COLUMNS) - 1
