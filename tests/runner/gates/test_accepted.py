"""D7: the PM's accept of a completed outcome is identifiable; a loop accept is not."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

from amoeba.runner.gates.accepted import AcceptedOutcome, accepted_by_pm
from amoeba.store import (
    PARAM_CONTINUATION,
    BlockedKind,
    BlockedState,
    CommandKind,
    JournalEntry,
    JournalOutcome,
    Resolution,
    ResolutionOutcome,
)
from runner.dispatch.dispatch_support import FIRST, entry

WHEN = datetime(2026, 10, 26, tzinfo=UTC)


def _completed(*verdict_ids: str, **parameters: object) -> JournalEntry:
    base = entry(
        CommandKind.SQ_RUN,
        "step",
        FIRST,
        JournalOutcome.COMPLETED,
        outcome_text="completed",
    )
    result = {**(base.result or {}), "verdict_ids": list(verdict_ids)}
    return replace(base, result=result, parameters={**base.parameters, **parameters})


def _blocked(
    decision: str | None = "accept",
    outcome: ResolutionOutcome | None = ResolutionOutcome.APPLIED,
) -> BlockedState:
    resolution = (
        None
        if decision is None
        else Resolution("pm", "detail", WHEN, decision=decision)
    )
    return BlockedState(
        id="blocked-1",
        node_id="step",
        kind=BlockedKind.HUMAN,
        context="escalated",
        resolution=resolution,
        runner_outcome=outcome,
    )


def test_an_applied_accept_of_a_completed_outcome_is_identified() -> None:
    run = _completed("v-1", "v-2")

    accepted = accepted_by_pm([run], _blocked())

    assert accepted == AcceptedOutcome("blocked-1", run.id, ("v-1", "v-2"))


def test_a_rejected_accept_is_not_counted() -> None:
    blocked = _blocked(outcome=ResolutionOutcome.REJECTED)

    assert accepted_by_pm([_completed("v-1")], blocked) is None


def test_an_accept_nobody_answered_yet_is_not_counted() -> None:
    assert accepted_by_pm([_completed("v-1")], _blocked(outcome=None)) is None


def test_a_rerun_is_not_an_accept() -> None:
    assert accepted_by_pm([_completed("v-1")], _blocked("rerun")) is None


def test_a_loop_accept_is_not_counted() -> None:
    continuation = _completed("v-1", **{PARAM_CONTINUATION: "accept"})

    assert accepted_by_pm([_completed("v-0"), continuation], _blocked()) is None


def test_no_blocked_state_is_not_an_accept() -> None:
    assert accepted_by_pm([_completed("v-1")], None) is None


def test_an_unresolved_blocked_state_is_not_an_accept() -> None:
    assert accepted_by_pm([_completed("v-1")], _blocked(None, None)) is None


def test_an_accept_followed_by_a_newer_run_that_did_not_complete_is_not_counted() -> (
    None
):
    newer = entry(
        CommandKind.SQ_RUN, "step", FIRST, JournalOutcome.FAILED, outcome_text="failed"
    )

    assert accepted_by_pm([_completed("v-1"), newer], _blocked()) is None


def test_the_latest_run_entry_is_the_one_that_was_accepted() -> None:
    older, newer = _completed("v-old"), _completed("v-new")

    accepted = accepted_by_pm([older, newer], _blocked())

    assert accepted is not None and accepted.entry_id == newer.id
    assert accepted.verdict_ids == ("v-new",)


def test_a_step_with_no_run_has_nothing_accepted() -> None:
    assert accepted_by_pm([], _blocked()) is None
