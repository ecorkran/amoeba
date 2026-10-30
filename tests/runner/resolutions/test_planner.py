"""``ContinuationPlanner``: one action per eligible step, and waiting on holders."""

from __future__ import annotations

from pathlib import Path

import pytest

from amoeba.runner.decide import (
    Action,
    BlockDispatch,
    LaunchRun,
    Planner,
    ResumeRun,
    decide,
)
from amoeba.runner.dispatch.params import PARAM_DISPATCH_CHECK
from amoeba.runner.dispatch.planner import DispatchPlanner
from amoeba.runner.dispatch.state import DispatchState
from amoeba.runner.faults import FaultKind
from amoeba.runner.gates.predispatch import Block
from amoeba.runner.resolutions.planner import ContinuationPlanner
from amoeba.runner.resolutions.vocabulary import ResumeCause
from amoeba.store import (
    PARAM_CHECKOUT,
    BlockedKind,
    BlockedState,
    CommandKind,
    JournalEntry,
    Resolution,
    ResolutionOutcome,
)
from runner.dispatch.dispatch_support import (
    FIRST,
    OK_EVIDENCE,
    SECOND,
    entry,
    facts,
    view_of,
)

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


def test_resume_resumes_the_continued_run() -> None:
    continued = _continued()
    view = view_of({"a": _facts(DispatchState.RESUME, "resume", continued)})

    assert PLANNER.plan(view) == [
        ResumeRun(
            "a",
            "run-a",
            continued.id,
            "b-1",
            FIRST,
            cause=ResumeCause.RESOLUTION,
            journal_extra={PARAM_DISPATCH_CHECK: dict(OK_EVIDENCE)},
        )
    ]


def test_the_runs_own_checkout_is_used() -> None:
    continued = _continued(checkout=SECOND)
    view = view_of({"a": _facts(DispatchState.RESUME, "resume", continued, SECOND)})

    [action] = PLANNER.plan(view)

    assert isinstance(action, ResumeRun)
    assert action.checkout == Path(str(continued.parameters[PARAM_CHECKOUT]))


def test_one_action_per_eligible_step() -> None:
    a, b = _continued("a", FIRST), _continued("b", SECOND)
    view = view_of(
        {
            "a": _facts(DispatchState.RESUME, "resume", a),
            "b": _facts(DispatchState.RESUME, "resume", b, SECOND),
            "c": facts(DispatchState.READY, FIRST),
        },
        holders={FIRST: frozenset({"a"}), SECOND: frozenset({"b"})},
    )

    actions = PLANNER.plan(view)

    assert [type(action) for action in actions] == [ResumeRun, ResumeRun]


def test_a_checkout_held_only_by_the_step_itself_does_not_wait() -> None:
    view = view_of(
        {"a": _facts(DispatchState.RESUME, "resume", _continued())},
        holders={FIRST: frozenset({"a"})},
    )

    assert len(PLANNER.plan(view)) == 1


def test_a_checkout_held_by_another_node_waits() -> None:
    view = view_of(
        {"a": _facts(DispatchState.RESUME, "resume", _continued())},
        holders={FIRST: frozenset({"a", "other"})},
    )

    assert PLANNER.plan(view) == []


def test_a_step_that_is_not_current_gets_nothing() -> None:
    view = view_of(
        {"a": _facts(DispatchState.RESUME, "resume", _continued())}, current=[]
    )

    assert PLANNER.plan(view) == []


def test_steps_in_other_states_get_nothing() -> None:
    states = [
        DispatchState.READY,
        DispatchState.READY,
        DispatchState.IN_FLIGHT,
    ]
    view = view_of({f"s{i}": facts(state) for i, state in enumerate(states)})

    assert PLANNER.plan(view) == []


def test_a_resume_without_its_continued_entry_is_a_defect() -> None:
    view = view_of({"a": facts(DispatchState.RESUME, resolution=_resolution("resume"))})

    with pytest.raises(ValueError, match="without its entry or decision"):
        PLANNER.plan(view)


def test_the_two_planners_never_act_on_the_same_step() -> None:
    states = {
        "a": _facts(DispatchState.RESUME, "resume", _continued("a")),
        "b": facts(DispatchState.READY, SECOND),
    }
    view = view_of(states)

    def acted(planner: Planner) -> set[str]:
        return {action.node_id for action in planner.plan(view)}

    assert acted(PLANNER) == {"a"}
    assert acted(DispatchPlanner()) == {"b"}


def test_decide_accepts_the_new_actions_for_current_steps() -> None:
    view = view_of({"a": _facts(DispatchState.RESUME, "resume", _continued())})

    actions: list[Action] = decide(view, [PLANNER, DispatchPlanner()])

    assert [type(action) for action in actions] == [ResumeRun]


def test_decide_refuses_a_continuation_for_a_step_that_is_not_current() -> None:
    class Stray:
        def plan(self, view: object) -> list[Action]:
            return [
                ResumeRun("a", "run-a", "e", "b", FIRST, cause=ResumeCause.RESOLUTION)
            ]

    view = view_of({"a": facts(DispatchState.RESUME)}, current=[])

    with pytest.raises(ValueError, match="not a current slice"):
        decide(view, [Stray()])


def test_launch_runs_are_not_continuations() -> None:
    assert not issubclass(LaunchRun, ResumeRun)


# -- slice 128, D5: a resume goes ahead only on a passed check -------------------


def test_a_resume_with_no_result_waits() -> None:
    continued = _continued()
    view = view_of({"a": _facts(DispatchState.RESUME, "resume", continued)}, checks={})

    assert ContinuationPlanner().plan(view) == []


def test_a_blocked_resume_gives_block_dispatch() -> None:
    continued = _continued()
    block = Block(FaultKind.CHECKOUT_BRANCH, "wrong branch", {"branch": "x"})
    view = view_of(
        {"a": _facts(DispatchState.RESUME, "resume", continued)}, checks={"a": block}
    )

    assert ContinuationPlanner().plan(view) == [BlockDispatch("a", block)]
