"""``ContinuationPlanner``: one action per eligible step, and waiting on holders."""

from __future__ import annotations

from pathlib import Path

import pytest

from amoeba.runner.decide import (
    Action,
    LaunchRun,
    ObserveRun,
    Planner,
    ResumeRun,
    decide,
)
from amoeba.runner.dispatch.planner import DispatchPlanner
from amoeba.runner.dispatch.state import DispatchState
from amoeba.runner.resolutions.planner import ContinuationPlanner
from amoeba.runner.resolutions.vocabulary import Continuation
from amoeba.store import (
    PARAM_CHECKOUT,
    BlockedKind,
    BlockedState,
    CommandKind,
    JournalEntry,
    Resolution,
    ResolutionOutcome,
)
from runner.dispatch.dispatch_support import FIRST, SECOND, entry, facts, view_of

PLANNER = ContinuationPlanner()


def _resolution(decision: str, state_id: str = "b-1") -> BlockedState:
    return BlockedState(
        id=state_id,
        node_id="a",
        kind=BlockedKind.HUMAN,
        context="decide",
        resolution=Resolution(resolved_by="pm", detail="go", decision=decision),
        runner_outcome=ResolutionOutcome.APPLIED,
    )


def _continued(node_id: str = "a", checkout: Path = FIRST) -> JournalEntry:
    return entry(CommandKind.SQ_RUN, node_id, checkout, run_id=f"run-{node_id}")


def _facts(
    state: DispatchState, decision: str, continued: JournalEntry, checkout: Path = FIRST
):
    return facts(state, checkout, resolution=_resolution(decision), continues=continued)


@pytest.mark.parametrize(
    ("decision", "expected"),
    [("retry", Continuation.RETRY), ("accept", Continuation.ACCEPT)],
)
def test_retry_and_accept_resume_the_continued_run(
    decision: str, expected: Continuation
) -> None:
    continued = _continued()
    view = view_of({"a": _facts(DispatchState.RESUME, decision, continued)})

    assert PLANNER.plan(view) == [
        ResumeRun("a", "run-a", expected, continued.id, "b-1", FIRST)
    ]


def test_handled_observes_the_continued_run() -> None:
    continued = _continued()
    view = view_of({"a": _facts(DispatchState.REOBSERVE, "handled", continued)})

    assert PLANNER.plan(view) == [ObserveRun("a", "run-a", continued.id, "b-1", FIRST)]


def test_the_runs_own_checkout_is_used() -> None:
    continued = _continued(checkout=SECOND)
    view = view_of({"a": _facts(DispatchState.RESUME, "retry", continued, SECOND)})

    [action] = PLANNER.plan(view)

    assert isinstance(action, ResumeRun)
    assert action.checkout == Path(str(continued.parameters[PARAM_CHECKOUT]))


def test_one_action_per_eligible_step() -> None:
    a, b = _continued("a", FIRST), _continued("b", SECOND)
    view = view_of(
        {
            "a": _facts(DispatchState.RESUME, "retry", a),
            "b": _facts(DispatchState.REOBSERVE, "handled", b, SECOND),
            "c": facts(DispatchState.NEEDS_POINTER, FIRST),
        },
        holders={FIRST: frozenset({"a"}), SECOND: frozenset({"b"})},
    )

    actions = PLANNER.plan(view)

    assert [type(action) for action in actions] == [ResumeRun, ObserveRun]


def test_a_checkout_held_only_by_the_step_itself_does_not_wait() -> None:
    view = view_of(
        {"a": _facts(DispatchState.RESUME, "retry", _continued())},
        holders={FIRST: frozenset({"a"})},
    )

    assert len(PLANNER.plan(view)) == 1


def test_a_checkout_held_by_another_node_waits() -> None:
    view = view_of(
        {"a": _facts(DispatchState.RESUME, "retry", _continued())},
        holders={FIRST: frozenset({"a", "other"})},
    )

    assert PLANNER.plan(view) == []


def test_a_step_that_is_not_current_gets_nothing() -> None:
    view = view_of(
        {"a": _facts(DispatchState.RESUME, "retry", _continued())}, current=[]
    )

    assert PLANNER.plan(view) == []


def test_steps_in_other_states_get_nothing() -> None:
    states = [
        DispatchState.POINTED,
        DispatchState.NEEDS_POINTER,
        DispatchState.IN_FLIGHT,
    ]
    view = view_of({f"s{i}": facts(state) for i, state in enumerate(states)})

    assert PLANNER.plan(view) == []


def test_a_resume_without_its_continued_entry_is_a_defect() -> None:
    view = view_of({"a": facts(DispatchState.RESUME, resolution=_resolution("retry"))})

    with pytest.raises(ValueError, match="without its entry or decision"):
        PLANNER.plan(view)


def test_the_two_planners_never_act_on_the_same_step() -> None:
    states = {
        "a": _facts(DispatchState.RESUME, "retry", _continued("a")),
        "b": facts(DispatchState.POINTED, SECOND),
    }
    view = view_of(states)

    def acted(planner: Planner) -> set[str]:
        return {action.node_id for action in planner.plan(view)}

    assert acted(PLANNER) == {"a"}
    assert acted(DispatchPlanner()) == {"b"}


def test_decide_accepts_the_new_actions_for_current_steps() -> None:
    view = view_of({"a": _facts(DispatchState.RESUME, "retry", _continued())})

    actions: list[Action] = decide(view, [PLANNER, DispatchPlanner()])

    assert [type(action) for action in actions] == [ResumeRun]


def test_decide_refuses_a_continuation_for_a_step_that_is_not_current() -> None:
    class Stray:
        def plan(self, view: object) -> list[Action]:
            return [ObserveRun("a", "run-a", "e", "b", FIRST)]

    view = view_of({"a": facts(DispatchState.RESUME)}, current=[])

    with pytest.raises(ValueError, match="not a current step"):
        decide(view, [Stray()])


def test_launch_runs_are_not_continuations() -> None:
    assert not issubclass(LaunchRun, (ResumeRun, ObserveRun))
