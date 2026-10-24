"""D3, D4: one action per checkout, launches before pointer writes."""

from __future__ import annotations

from pathlib import Path

import pytest

from amoeba.runner.decide import LaunchRun, WriteSlicePointer
from amoeba.runner.dispatch.checkout import Checkout, CheckoutUnresolved
from amoeba.runner.dispatch.params import MERGE_DISABLED, PARAM_MERGE
from amoeba.runner.dispatch.planner import DispatchPlanner
from amoeba.runner.dispatch.state import DispatchState
from amoeba.runner.lifecycle.steps import LifecycleStep
from amoeba.store import CommandKind, JournalOutcome, JournalResolver
from runner.dispatch.dispatch_support import (
    CF_PROJECT,
    FIRST,
    SECOND,
    entry,
    facts,
    view_of,
)

PLANNER = DispatchPlanner()


def test_a_pointed_step_launches_its_pipeline() -> None:
    view = view_of({"a": facts(DispatchState.POINTED, step=LifecycleStep.TASKS)})

    assert PLANNER.plan(view) == [LaunchRun("a", "P5", {"slice": "125"}, FIRST)]


@pytest.mark.parametrize(
    ("step", "pipeline"),
    [
        (LifecycleStep.SLICE_DESIGN, "P4"),
        (LifecycleStep.TASKS, "P5"),
        (LifecycleStep.IMPLEMENTATION, "P6"),
    ],
)
def test_each_step_launches_its_pipeline_and_p6_never_merges(
    step: LifecycleStep, pipeline: str
) -> None:
    view = view_of({"a": facts(DispatchState.POINTED, step=step)})

    [action] = PLANNER.plan(view)

    assert isinstance(action, LaunchRun) and action.pipeline == pipeline
    has_merge = PARAM_MERGE in action.params
    assert has_merge is (step is LifecycleStep.IMPLEMENTATION)
    if has_merge:
        assert action.params[PARAM_MERGE] == MERGE_DISABLED


def test_a_step_that_needs_a_pointer_writes_it() -> None:
    view = view_of({"a": facts(DispatchState.NEEDS_POINTER, SECOND, slice_index=130)})

    [action] = PLANNER.plan(view)

    assert action == WriteSlicePointer("a", CF_PROJECT, 130, Checkout(SECOND, None))


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
        "a", "P5", {"slice": "125"}, FIRST, run_id="run-old", reissue_of=old.id
    )


def test_a_reissue_without_its_old_entry_is_refused() -> None:
    view = view_of({"a": facts(DispatchState.REISSUE)})

    with pytest.raises(ValueError, match="no old entry"):
        PLANNER.plan(view)


@pytest.mark.parametrize(
    "state", [DispatchState.IN_FLIGHT, DispatchState.AWAITING_ROUTING]
)
def test_in_flight_and_awaiting_routing_get_nothing(state: DispatchState) -> None:
    assert PLANNER.plan(view_of({"a": facts(state)})) == []


def test_an_unresolved_checkout_gets_nothing() -> None:
    view = view_of({"a": facts(DispatchState.NEEDS_POINTER, CheckoutUnresolved("x"))})

    assert PLANNER.plan(view) == []


def test_a_step_without_dispatch_facts_gets_nothing() -> None:
    view = view_of({}, current=["human-step"])

    assert PLANNER.plan(view) == []


def test_a_step_that_is_not_current_gets_nothing() -> None:
    view = view_of({"a": facts(DispatchState.POINTED)}, current=[])

    assert PLANNER.plan(view) == []


def test_a_held_checkout_gives_a_pointer_writer_nothing() -> None:
    view = view_of({"a": facts(DispatchState.NEEDS_POINTER)}, held=[FIRST])

    assert PLANNER.plan(view) == []


def test_a_held_checkout_gives_a_reissue_nothing() -> None:
    old = entry(CommandKind.SQ_RUN, "a", outcome=JournalOutcome.NOT_APPLIED)
    view = view_of({"a": facts(DispatchState.REISSUE, reissue_of=old)}, held=[FIRST])

    assert PLANNER.plan(view) == []


def test_the_pointed_step_launches_in_the_checkout_its_claim_holds() -> None:
    steps = {
        "first": facts(DispatchState.POINTED, slice_index=125),
        "second": facts(DispatchState.NEEDS_POINTER, slice_index=126),
    }

    actions = PLANNER.plan(view_of(steps, held=[FIRST]))

    assert [a.node_id for a in actions] == ["first"]
    assert isinstance(actions[0], LaunchRun)


def test_the_second_slice_waits_while_the_first_runs_or_is_paused() -> None:
    """Hold (in flight, paused, or claimed) is in ``held_checkouts``: nothing starts."""
    view = view_of(
        {"second": facts(DispatchState.NEEDS_POINTER, slice_index=126)}, held=[FIRST]
    )

    assert PLANNER.plan(view) == []


def test_a_slice_in_another_worktree_is_planned_meanwhile() -> None:
    steps = {
        "first": facts(DispatchState.NEEDS_POINTER, FIRST, slice_index=125),
        "second": facts(DispatchState.NEEDS_POINTER, SECOND, slice_index=225),
    }

    actions = PLANNER.plan(view_of(steps, held=[FIRST]))

    assert [a.node_id for a in actions] == ["second"]


def test_one_action_per_checkout_the_pointed_step_first() -> None:
    steps = {
        "early": facts(DispatchState.NEEDS_POINTER, slice_index=120),
        "late": facts(DispatchState.POINTED, slice_index=130),
    }

    actions = PLANNER.plan(view_of(steps))

    assert [a.node_id for a in actions] == ["late"]
    assert isinstance(actions[0], LaunchRun)


def test_otherwise_the_lowest_initiative_slice_and_step_goes_first() -> None:
    steps = {
        "later-slice": facts(DispatchState.NEEDS_POINTER, slice_index=130),
        "later-step": facts(
            DispatchState.NEEDS_POINTER,
            slice_index=125,
            step=LifecycleStep.IMPLEMENTATION,
        ),
        "first": facts(
            DispatchState.NEEDS_POINTER, slice_index=125, step=LifecycleStep.TASKS
        ),
        "other-initiative": facts(
            DispatchState.NEEDS_POINTER, slice_index=100, initiative_index=130
        ),
    }

    actions = PLANNER.plan(view_of(steps))

    assert [a.node_id for a in actions] == ["first"]


def test_checkouts_are_planned_independently_and_in_order() -> None:
    steps = {
        "b": facts(DispatchState.NEEDS_POINTER, SECOND, slice_index=225),
        "a": facts(DispatchState.POINTED, FIRST, slice_index=125),
    }

    actions = PLANNER.plan(view_of(steps))

    assert [a.node_id for a in actions] == ["a", "b"], "launches first"


def test_a_checkout_path_is_compared_not_its_spelling() -> None:
    steps = {"a": facts(DispatchState.NEEDS_POINTER, Path("/work/amoeba/"))}

    assert PLANNER.plan(view_of(steps, held=[Path("/work/amoeba")])) == []
