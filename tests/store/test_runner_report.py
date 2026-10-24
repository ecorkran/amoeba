"""``record_runner_report``: verdict, ledger row, and resolution as one commit."""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from evidence_harness import PROJECT, seed_node, verdict_input
from sq_run_fixtures import sq_run_parameters

from amoeba.store import (
    CommandKind,
    DetectionInput,
    DetectionOutcome,
    InvalidTransitionError,
    JournalEntry,
    JournalOutcome,
    JournalResolver,
    Store,
    StoreError,
)

RUN_RESULT = {"run_id": "run-20261019-review-aaaa1111"}
OTHER_PROJECT = "elsewhere"


def _issue(
    store: Store,
    node_id: str,
    kind: CommandKind = CommandKind.SQ_RUN,
) -> JournalEntry:
    # Carries the required keys of both kinds; extra keys are stored verbatim.
    parameters = sq_run_parameters(
        {
            "pipeline": "review",
            "params": {},
            "project": "p",
            "expected": "x",
            "checkout": "/work/p",
        },
        run_id=RUN_RESULT["run_id"],
    )
    return store.journal_issue(node_id, kind=kind, parameters=parameters)


def _detection(
    outcome: DetectionOutcome = DetectionOutcome.RUNNER_ISSUED,
    project_id: str = PROJECT,
) -> DetectionInput:
    return DetectionInput(
        project_id=project_id,
        path="/r/review.md",
        digest="d1",
        outcome=outcome,
        record_id="v-1",
    )


@dataclass(frozen=True)
class _Snapshot:
    """Everything a refused or rolled-back call must leave unchanged."""

    verdicts: int
    detections: int
    entry: JournalEntry | None


def _snapshot(store: Store, entry_id: str) -> _Snapshot:
    return _Snapshot(
        verdicts=len(store.verdicts(PROJECT)),
        detections=len(store.detections(PROJECT)),
        entry=store.journal_entry(entry_id),
    )


def test_one_call_writes_the_verdict_the_ledger_row_and_the_resolution(
    store: Store,
) -> None:
    node_id = seed_node(store)
    entry = _issue(store, node_id)

    record = store.record_runner_report(
        entry.id, verdict_input("v-1", node_id), _detection(), result=RUN_RESULT
    )

    assert store.verdicts(PROJECT) == [record]
    [row] = store.detections(PROJECT)
    assert (row.outcome, row.verdict_id, row.node_id) == (
        DetectionOutcome.RUNNER_ISSUED,
        "v-1",
        node_id,
    )
    resolved = store.journal_entry(entry.id)
    assert resolved is not None
    assert resolved.outcome is JournalOutcome.COMPLETED
    assert resolved.resolved_by is JournalResolver.ISSUER
    assert resolved.result == RUN_RESULT
    assert store.recorded_result_run_ids(PROJECT) == {RUN_RESULT["run_id"]: entry.id}


def test_a_failure_while_resolving_rolls_back_everything(
    store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    node_id = seed_node(store)
    entry = _issue(store, node_id)
    before = _snapshot(store, entry.id)

    def fail(*_args: object) -> None:
        raise StoreError("resolve refused")

    monkeypatch.setattr(store, "_resolve_entry_within", fail)

    with pytest.raises(StoreError, match="resolve refused"):
        store.record_runner_report(
            entry.id, verdict_input("v-1", node_id), _detection(), result=RUN_RESULT
        )

    assert _snapshot(store, entry.id) == before
    assert before.entry is not None and not before.entry.is_resolved


def test_a_ledger_key_already_present_is_kept_and_the_entry_still_resolves(
    store: Store,
) -> None:
    node_id = seed_node(store)
    entry = _issue(store, node_id)
    existing = store.record_detection(_detection(DetectionOutcome.INGESTED))

    record = store.record_runner_report(
        entry.id, verdict_input("v-1", node_id), _detection(), result=RUN_RESULT
    )

    assert store.detections(PROJECT) == [existing]
    assert store.verdicts(PROJECT) == [record]
    resolved = store.journal_entry(entry.id)
    assert resolved is not None and resolved.is_resolved


def test_a_verdict_already_recorded_is_returned_and_the_rest_still_happens(
    store: Store,
) -> None:
    node_id = seed_node(store)
    entry = _issue(store, node_id)
    first = store.record_verdict(verdict_input("v-1", node_id), project_id=PROJECT)

    record = store.record_runner_report(
        entry.id, verdict_input("v-1", node_id), _detection(), result=RUN_RESULT
    )

    assert record == first
    assert len(store.verdicts(PROJECT)) == 1
    [row] = store.detections(PROJECT)
    assert row.outcome is DetectionOutcome.RUNNER_ISSUED
    resolved = store.journal_entry(entry.id)
    assert resolved is not None and resolved.is_resolved


# --------------------------------------------------------------------------
# Refusals: each writes nothing
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "outcome",
    [o for o in DetectionOutcome if o is not DetectionOutcome.RUNNER_ISSUED],
)
def test_another_detection_outcome_is_refused(
    store: Store, outcome: DetectionOutcome
) -> None:
    node_id = seed_node(store)
    entry = _issue(store, node_id)
    before = _snapshot(store, entry.id)

    with pytest.raises(ValueError, match="runner_issued"):
        store.record_runner_report(
            entry.id,
            verdict_input("v-1", node_id),
            _detection(outcome),
            result=RUN_RESULT,
        )

    assert _snapshot(store, entry.id) == before


def test_a_resolved_entry_is_refused(store: Store) -> None:
    node_id = seed_node(store)
    entry = _issue(store, node_id)
    store.journal_resolve(entry.id, outcome=JournalOutcome.FAILED)
    before = _snapshot(store, entry.id)

    with pytest.raises(InvalidTransitionError, match="already resolved"):
        store.record_runner_report(
            entry.id, verdict_input("v-1", node_id), _detection(), result=RUN_RESULT
        )

    assert _snapshot(store, entry.id) == before


def test_an_unknown_entry_is_refused(store: Store) -> None:
    node_id = seed_node(store)

    with pytest.raises(InvalidTransitionError, match="does not exist"):
        store.record_runner_report(
            "no-such-entry",
            verdict_input("v-1", node_id),
            _detection(),
            result=RUN_RESULT,
        )

    assert store.verdicts(PROJECT) == []
    assert store.detections(PROJECT) == []


def test_an_entry_of_a_non_review_kind_is_refused(store: Store) -> None:
    node_id = seed_node(store)
    entry = _issue(store, node_id, CommandKind.CF_WRITE)
    before = _snapshot(store, entry.id)

    with pytest.raises(InvalidTransitionError, match="does not produce a review"):
        store.record_runner_report(
            entry.id, verdict_input("v-1", node_id), _detection(), result=RUN_RESULT
        )

    assert _snapshot(store, entry.id) == before


def test_an_entry_in_another_project_is_refused(store: Store) -> None:
    node_id = seed_node(store)
    other_node = seed_node(store, OTHER_PROJECT)
    entry = _issue(store, other_node)
    before = _snapshot(store, entry.id)

    with pytest.raises(InvalidTransitionError, match="belongs to project"):
        store.record_runner_report(
            entry.id, verdict_input("v-1", node_id), _detection(), result=RUN_RESULT
        )

    assert _snapshot(store, entry.id) == before


def test_an_sq_run_result_without_a_run_id_is_refused(store: Store) -> None:
    node_id = seed_node(store)
    entry = _issue(store, node_id)
    before = _snapshot(store, entry.id)

    with pytest.raises(ValueError, match="run_id"):
        store.record_runner_report(
            entry.id, verdict_input("v-1", node_id), _detection(), result={}
        )

    assert _snapshot(store, entry.id) == before
