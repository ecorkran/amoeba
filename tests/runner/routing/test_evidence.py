"""``gather`` reads an ingested outcome back from the store, and writes nothing."""

from __future__ import annotations

from routing_helpers import TABLE, decision_input

from amoeba.process import RunOutcome
from amoeba.runner.routing.evidence import gather
from amoeba.runner.routing.inputs import RoutingInput
from amoeba.runner.routing.reduce import reduce
from amoeba.store import (
    FindingChange,
    FindingSeverity,
    ReviewVerdict,
    Store,
    VerdictStanding,
)
from runner.routing.entry_support import (
    PROJECT,
    StagedReview,
    concern,
    note,
    stage_node,
    stage_outcome,
)


def test_an_entry_with_recorded_verdicts_gathers_its_parts(store: Store) -> None:
    node_id = stage_node(store)
    review = StagedReview("v-1", findings=(concern("c1"), concern("c2"), note("n1")))
    entry = stage_outcome(store, node_id, reviews=(review,))

    evidence = gather(store, entry)

    [part] = evidence.parts
    assert part.verdict is ReviewVerdict.CONCERNS
    assert part.standing is VerdictStanding.STATED
    assert part.severity is FindingSeverity.CONCERN
    assert part.comparable is True
    assert part.routed_changes == (FindingChange.NEW, FindingChange.NEW)
    assert evidence.review_unreadable is False
    assert evidence.outcome == RunOutcome.COMPLETED.value


def test_an_entry_naming_a_missing_verdict_is_unreadable_not_an_exception(
    store: Store,
) -> None:
    node_id = stage_node(store)
    entry = stage_outcome(store, node_id, verdict_ids=["never-recorded"])

    evidence = gather(store, entry)

    assert evidence.review_unreadable is True
    assert evidence.parts == ()


def test_a_review_fault_is_carried(store: Store) -> None:
    node_id = stage_node(store)
    entry = stage_outcome(store, node_id, review_fault="the file would not parse")

    assert gather(store, entry).review_fault is True


def test_a_launch_failure_entry_gathers_no_parts(store: Store) -> None:
    node_id = stage_node(store)
    entry = stage_outcome(store, node_id, launch_failure="sq_missing")

    evidence = gather(store, entry)

    assert evidence.launch_failed is True
    assert evidence.outcome is None
    assert evidence.parts == ()
    assert evidence.checkpoint is None


def test_the_outcome_document_sections_are_carried(store: Store) -> None:
    node_id = stage_node(store)
    document = {
        "run_id": "run-20261025-p4-aaaa0001",
        "outcome": "paused",
        "checkpoint": {"kind": "loop_exhausted", "is_loop": True},
    }
    entry = stage_outcome(
        store, node_id, outcome=RunOutcome.PAUSED.value, document=document
    )

    evidence = gather(store, entry)

    assert evidence.checkpoint is not None
    assert evidence.checkpoint.kind == "loop_exhausted"
    assert evidence.failure is None


def test_attempts_are_counted_for_a_known_step_only(store: Store) -> None:
    known = stage_node(store, "slice_design")
    unknown = stage_node(store, "a_phase_cf_invented")
    missing = stage_node(store, None)

    assert gather(store, stage_outcome(store, known, run_id="run-a")).attempt_count == 0
    for node_id in (unknown, missing):
        entry = stage_outcome(store, node_id, run_id=f"run-{node_id}")
        assert gather(store, entry).attempt_count is None


def test_a_routed_attempt_is_counted_on_the_next_gather(store: Store) -> None:
    node_id = stage_node(store)
    first = stage_outcome(store, node_id, run_id="run-first")
    store.record_routing_decision(
        decision_input(node_id, first.id),
        table=TABLE,
        effect=None,
        attempt_step="slice_design",
    )
    second = stage_outcome(store, node_id, run_id="run-second")

    assert gather(store, second).attempt_count == 1


def test_gather_then_reduce_a_stated_pass(store: Store) -> None:
    node_id = stage_node(store)
    review = StagedReview("v-pass", verdict=ReviewVerdict.PASS)
    entry = stage_outcome(store, node_id, reviews=(review,))

    inputs = reduce(gather(store, entry))

    assert inputs.values[RoutingInput.VERDICT] == "pass"
    assert inputs.values[RoutingInput.STANDING] == "stated"
    assert inputs.attempt == 1


def test_recurring_note_does_not_recur(store: Store) -> None:
    node_id = stage_node(store)
    first = StagedReview("v-1", findings=(note("same note"),))
    again = StagedReview("v-2", findings=(note("same note"),))
    stage_outcome(store, node_id, run_id="run-1", reviews=(first,))
    entry = stage_outcome(store, node_id, run_id="run-2", reviews=(again,))

    assert reduce(gather(store, entry)).values[RoutingInput.RECURRENCE] == "clear"


def test_a_recurring_concern_recurs(store: Store) -> None:
    node_id = stage_node(store)
    first = StagedReview("v-1", findings=(concern("same concern"),))
    again = StagedReview("v-2", findings=(concern("same concern"),))
    stage_outcome(store, node_id, run_id="run-1", reviews=(first,))
    entry = stage_outcome(store, node_id, run_id="run-2", reviews=(again,))

    assert reduce(gather(store, entry)).values[RoutingInput.RECURRENCE] == "recurring"


def test_gather_writes_nothing(store: Store) -> None:
    node_id = stage_node(store)
    entry = stage_outcome(store, node_id)

    gather(store, entry)

    assert [e.id for e in store.unrouted_outcomes(PROJECT)] == [entry.id]


# -- slice 127: continuations -------------------------------------------------


def test_a_failed_resume_is_carried_and_wins_over_the_recorded_outcome(
    store: Store,
) -> None:
    node_id = stage_node(store)
    entry = stage_outcome(store, node_id, outcome="paused", resume_failure="refused")

    evidence = gather(store, entry)

    assert evidence.resume_failed is True
    assert reduce(evidence).values[RoutingInput.OUTCOME] == "resume_failed"


def test_an_ordinary_run_carries_no_continuation(store: Store) -> None:
    node_id = stage_node(store)
    entry = stage_outcome(store, node_id)

    evidence = gather(store, entry)

    assert evidence.continuation is None and evidence.continued_verdict_ids is None
    assert evidence.resume_failed is False


def test_an_accepted_loop_that_wrote_no_newer_review_is_review_accepted(
    store: Store,
) -> None:
    node_id = stage_node(store)
    paused = stage_outcome(
        store, node_id, outcome="paused", reviews=(StagedReview("v-1"),)
    )
    accepted = stage_outcome(
        store,
        node_id,
        run_id="run-20261025-p4-aaaa0001",
        verdict_ids=["v-1"],
        continuation=("accept", paused.id),
    )

    evidence = gather(store, accepted)

    assert (evidence.continuation, evidence.continued_verdict_ids) == (
        "accept",
        ("v-1",),
    )
    assert reduce(evidence).values[RoutingInput.REVIEW_ACCEPTED] == "true"


def test_an_accepted_loop_that_wrote_a_newer_review_is_not(store: Store) -> None:
    node_id = stage_node(store)
    paused = stage_outcome(
        store, node_id, outcome="paused", reviews=(StagedReview("v-1"),)
    )
    accepted = stage_outcome(
        store,
        node_id,
        reviews=(StagedReview("v-2"),),
        continuation=("accept", paused.id),
    )

    evidence = gather(store, accepted)

    assert reduce(evidence).values[RoutingInput.REVIEW_ACCEPTED] == "false"


def test_an_accept_whose_continued_entry_is_gone_is_unknown(store: Store) -> None:
    node_id = stage_node(store)
    accepted = stage_outcome(store, node_id, continuation=("accept", "no-such-entry"))

    evidence = gather(store, accepted)

    assert evidence.continued_verdict_ids is None
    assert reduce(evidence).values[RoutingInput.REVIEW_ACCEPTED] == "unknown"
