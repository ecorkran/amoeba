"""D3, D4: one action per checkout, launches before pointer writes."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from amoeba.runner.decide import (
    BlockDispatch,
    LaunchRun,
    ProjectView,
    ResumeRun,
)
from amoeba.runner.dispatch.checkout import CheckoutUnresolved
from amoeba.runner.dispatch.params import (
    PARAM_DISPATCH_CHECK,
)
from amoeba.runner.dispatch.planner import DispatchPlanner
from amoeba.runner.dispatch.state import DispatchState
from amoeba.runner.faults import FaultKind
from amoeba.runner.gates.predispatch import Block, Ok
from amoeba.runner.project_config import ProjectSettings
from amoeba.runner.resolutions.vocabulary import ResumeCause
from amoeba.runner.supervise import RESULT_OUTCOME_DOCUMENT
from amoeba.store import (
    PARAM_RUN_ID,
    CommandKind,
    JournalEntry,
    JournalOutcome,
    JournalResolver,
)
from runner.dispatch.dispatch_support import (
    FIRST,
    OK_EVIDENCE,
    SECOND,
    TEST_PIPELINE,
    entry,
    facts,
    view_of,
)

PLANNER = DispatchPlanner()


def test_a_ready_slice_launches_the_configured_pipeline() -> None:
    view = view_of({"a": facts(DispatchState.READY, slice_index=125)})

    assert PLANNER.plan(view) == [
        LaunchRun(
            "a",
            TEST_PIPELINE,
            {"slice": "125"},
            FIRST,
            journal_extra={PARAM_DISPATCH_CHECK: dict(OK_EVIDENCE)},
        )
    ]


def test_the_projects_params_ride_along_after_the_slice() -> None:
    settings = ProjectSettings(pipeline="p4567", params={"model": "opus"})
    view = view_of({"a": facts(DispatchState.READY, slice_index=7)}, settings=settings)

    [action] = PLANNER.plan(view)

    assert isinstance(action, LaunchRun) and action.pipeline == "p4567"
    assert action.params == {"slice": "7", "model": "opus"}


def test_a_project_with_no_pipeline_launches_nothing() -> None:
    view = view_of({"a": facts(DispatchState.READY)}, settings=ProjectSettings())

    assert PLANNER.plan(view) == []


def test_a_reissue_repeats_the_old_attempt_under_its_run_id() -> None:
    old = entry(
        CommandKind.SQ_RUN,
        "a",
        FIRST,
        JournalOutcome.NOT_APPLIED,
        resolved_by=JournalResolver.RECOVERY,
        run_id="run-old",
    )
    view = view_of({"a": facts(DispatchState.REISSUE, reissue_of=old)})

    [action] = PLANNER.plan(view)

    assert action == LaunchRun(
        "a",
        "P5",
        {"slice": "125"},
        FIRST,
        run_id="run-old",
        reissue_of=old.id,
        journal_extra={PARAM_DISPATCH_CHECK: dict(OK_EVIDENCE)},
    )


def test_a_reissue_keeps_the_policy_of_the_attempt_it_repeats() -> None:
    first = entry(
        CommandKind.SQ_RUN,
        "a",
        FIRST,
        JournalOutcome.NOT_APPLIED,
        resolved_by=JournalResolver.RECOVERY,
        run_id="run-old",
    )
    view = view_of({"a": facts(DispatchState.REISSUE, reissue_of=first)})

    [action] = PLANNER.plan(view)

    assert isinstance(action, LaunchRun)
    assert action.run_id == "run-old" and action.reissue_of == first.id


def test_a_reissue_without_its_old_entry_is_refused() -> None:
    view = view_of({"a": facts(DispatchState.REISSUE)})

    with pytest.raises(ValueError, match="no old entry"):
        PLANNER.plan(view)


def test_in_flight_gets_nothing() -> None:
    assert PLANNER.plan(view_of({"a": facts(DispatchState.IN_FLIGHT)})) == []


def test_an_unresolved_checkout_gets_nothing() -> None:
    view = view_of({"a": facts(DispatchState.READY, CheckoutUnresolved("x"))})

    assert PLANNER.plan(view) == []


def test_a_step_without_dispatch_facts_gets_nothing() -> None:
    view = view_of({}, current=["human-step"])

    assert PLANNER.plan(view) == []


def test_a_step_that_is_not_current_gets_nothing() -> None:
    view = view_of({"a": facts(DispatchState.READY)}, current=[])

    assert PLANNER.plan(view) == []


def test_a_held_checkout_gives_a_ready_step_nothing() -> None:
    view = view_of({"a": facts(DispatchState.READY)}, held=[FIRST])

    assert PLANNER.plan(view) == []


def test_a_held_checkout_gives_a_reissue_nothing() -> None:
    old = entry(CommandKind.SQ_RUN, "a", outcome=JournalOutcome.NOT_APPLIED)
    view = view_of({"a": facts(DispatchState.REISSUE, reissue_of=old)}, held=[FIRST])

    assert PLANNER.plan(view) == []


def test_the_second_slice_waits_while_the_first_runs_or_is_paused() -> None:
    """Hold (in flight, paused, or claimed) is in ``held_checkouts``: nothing starts."""
    view = view_of(
        {"second": facts(DispatchState.READY, slice_index=126)}, held=[FIRST]
    )

    assert PLANNER.plan(view) == []


def test_a_slice_in_another_worktree_is_planned_meanwhile() -> None:
    steps = {
        "first": facts(DispatchState.READY, FIRST, slice_index=125),
        "second": facts(DispatchState.READY, SECOND, slice_index=225),
    }

    actions = PLANNER.plan(view_of(steps, held=[FIRST]))

    assert [a.node_id for a in actions] == ["second"]


def test_the_lowest_initiative_and_slice_goes_first() -> None:
    steps = {
        "later-slice": facts(DispatchState.READY, slice_index=130),
        "first": facts(DispatchState.READY, slice_index=125),
        "other-initiative": facts(
            DispatchState.READY, slice_index=100, initiative_index=130
        ),
    }

    actions = PLANNER.plan(view_of(steps))

    assert [a.node_id for a in actions] == ["first"]


def test_checkouts_are_planned_independently_and_in_order() -> None:
    steps = {
        "b": facts(DispatchState.READY, SECOND, slice_index=225),
        "a": facts(DispatchState.READY, FIRST, slice_index=125),
    }

    actions = PLANNER.plan(view_of(steps))

    assert [a.node_id for a in actions] == ["a", "b"], "launches first"


def test_a_checkout_path_is_compared_not_its_spelling() -> None:
    steps = {"a": facts(DispatchState.READY, Path("/work/amoeba/"))}

    assert PLANNER.plan(view_of(steps, held=[Path("/work/amoeba")])) == []


# -- slice 128, D5: a launch goes ahead only on a passed check ------------------


def _old_for(state: DispatchState) -> JournalEntry | None:
    """The attempt a reissue repeats; a pointed step repeats nothing."""
    if state is not DispatchState.REISSUE:
        return None
    return entry(
        CommandKind.SQ_RUN,
        "a",
        FIRST,
        JournalOutcome.NOT_APPLIED,
        resolved_by=JournalResolver.RECOVERY,
    )


@pytest.mark.parametrize("state", [DispatchState.READY, DispatchState.REISSUE])
def test_a_launch_with_no_result_does_nothing(state: DispatchState) -> None:
    view = view_of({"a": facts(state, reissue_of=_old_for(state))}, checks={})

    assert PLANNER.plan(view) == []


@pytest.mark.parametrize("state", [DispatchState.READY, DispatchState.REISSUE])
def test_a_blocked_check_gives_block_dispatch_and_no_launch(
    state: DispatchState,
) -> None:
    block = Block(FaultKind.CHECKOUT_DIRTY, "dirty", {"path_count": 1})
    view = view_of({"a": facts(state, reissue_of=_old_for(state))}, checks={"a": block})

    assert PLANNER.plan(view) == [BlockDispatch("a", block)]


def test_a_reissue_records_this_ticks_check() -> None:
    first = entry(
        CommandKind.SQ_RUN,
        "a",
        FIRST,
        JournalOutcome.NOT_APPLIED,
        resolved_by=JournalResolver.RECOVERY,
    )
    evidence = {**OK_EVIDENCE, "head": "newer"}
    view = view_of(
        {"a": facts(DispatchState.REISSUE, reissue_of=first)},
        checks={"a": Ok(evidence)},
    )

    [action] = PLANNER.plan(view)

    assert isinstance(action, LaunchRun)
    assert action.journal_extra == {PARAM_DISPATCH_CHECK: evidence}


# -- automatic resume (slice 132, D5) -------------------------------------------

RESETS_AT = datetime(2026, 10, 29, 18, 0, tzinfo=UTC)


def _stopped(document: dict[str, object], checkout: Path = FIRST) -> JournalEntry:
    """A resolved run entry holding the outcome document it was resolved with."""
    run = entry(
        CommandKind.SQ_RUN, "a", checkout, JournalOutcome.COMPLETED, outcome_text="x"
    )
    return replace(run, result={RESULT_OUTCOME_DOCUMENT: document})


_ORPHANED: dict[str, object] = {"run_id": "run-a", "outcome": "orphaned"}
_PROVIDER_ERROR: dict[str, object] = {
    "run_id": "run-a",
    "outcome": "failed",
    "failure": {"kind": "provider_error", "step": "design-0"},
}
_STALL: dict[str, object] = {
    "run_id": "run-a",
    "outcome": "failed",
    "failure": {"kind": "stall", "step": "design-0"},
}
_USAGE_LIMIT: dict[str, object] = {
    "run_id": "run-a",
    "outcome": "paused",
    "checkpoint": {
        "kind": "usage_limit",
        "step": "design-0",
        "resets_at": RESETS_AT.isoformat(),
    },
}


def _resume_view(
    stopped: JournalEntry, now: datetime = RESETS_AT, **kw: object
) -> ProjectView:
    step_facts = facts(DispatchState.AUTO_RESUME, FIRST, continues=stopped)
    return replace(view_of({"a": step_facts}, **kw), now=now)  # type: ignore[arg-type]


@pytest.mark.parametrize("document", [_ORPHANED, _PROVIDER_ERROR, _STALL])
def test_an_orphaned_provider_error_or_stall_outcome_is_resumed(
    document: dict[str, object],
) -> None:
    stopped = _stopped(document)

    [action] = PLANNER.plan(_resume_view(stopped))

    assert action == ResumeRun(
        "a",
        stopped.parameters[PARAM_RUN_ID],  # type: ignore[arg-type]
        stopped.id,
        None,
        FIRST,
        cause=ResumeCause.TRANSIENT,
        journal_extra={PARAM_DISPATCH_CHECK: dict(OK_EVIDENCE)},
    )


def test_a_usage_limit_pause_waits_for_its_reset_time() -> None:
    stopped = _stopped(_USAGE_LIMIT)

    assert PLANNER.plan(_resume_view(stopped, RESETS_AT - timedelta(seconds=1))) == []
    assert len(PLANNER.plan(_resume_view(stopped, RESETS_AT))) == 1


def test_a_resume_in_a_checkout_held_by_another_node_waits() -> None:
    stopped = _stopped(_STALL)

    view = _resume_view(stopped, holders={FIRST: frozenset({"a", "other"})})

    assert PLANNER.plan(view) == []


def test_a_resume_in_a_checkout_held_only_by_itself_goes_ahead() -> None:
    stopped = _stopped(_STALL)

    view = _resume_view(stopped, holders={FIRST: frozenset({"a"})})

    assert len(PLANNER.plan(view)) == 1


def test_a_resume_that_is_not_current_gets_nothing() -> None:
    stopped = _stopped(_STALL)
    step_facts = facts(DispatchState.AUTO_RESUME, FIRST, continues=stopped)
    view = replace(view_of({"a": step_facts}, current=[]), now=RESETS_AT)

    assert PLANNER.plan(view) == []


def test_a_failed_check_blocks_the_resume() -> None:
    stopped = _stopped(_STALL)
    block = Block(FaultKind.CHECKOUT_DIRTY, "dirty", {"path_count": 1})

    view = _resume_view(stopped, checks={"a": block})

    assert PLANNER.plan(view) == [BlockDispatch("a", block)]


def test_a_resume_without_a_check_waits_for_it() -> None:
    assert PLANNER.plan(_resume_view(_stopped(_STALL), checks={})) == []
