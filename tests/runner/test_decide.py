"""The decide stage is pure, ordered and refuses two actions for one node."""

from __future__ import annotations

import dataclasses
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from amoeba.runner.decide import (
    Action,
    BlockDispatch,
    LaunchRun,
    ProjectView,
    ResumeRun,
    decide,
)
from amoeba.runner.dispatch.checkout_check import Block, Ok
from amoeba.runner.faults import FaultKind
from amoeba.runner.lifecycle.tree import LifecycleTree
from amoeba.runner.resolutions.vocabulary import ResumeCause
from amoeba.store import DesiredState, Node
from runner.intent.rows_support import row
from runner.lifecycle.tree_support import TreeBuilder
from runner.tick_support import view_for

NOW = datetime(2026, 10, 23, tzinfo=UTC)


def _view() -> ProjectView:
    return view_for(LifecycleTree(()))


def _launch(node_id: str) -> LaunchRun:
    return LaunchRun(node_id, "noop", {"k": "v"}, Path("/work"))


class Fixed:
    def __init__(self, *actions: Action) -> None:
        self._actions = actions
        self.views: list[ProjectView] = []

    def plan(self, view: ProjectView) -> Sequence[Action]:
        self.views.append(view)
        return self._actions


@dataclass
class Steps:
    """Two initiatives' first slices, ready, with the project driven."""

    builder: TreeBuilder
    first: Node
    second: Node
    first_owner: Node
    second_owner: Node

    def view(self, *rows: DesiredState) -> ProjectView:
        """A driven view whose current steps have passed their pre-dispatch check."""
        view = view_for(self.builder.tree(), rows or (row(drive=True),))
        passed = {node.id: Ok({"target": "main"}) for node in view.current_slices}
        return replace(view, dispatch_checks=passed)


@pytest.fixture
def steps() -> Iterator[Steps]:
    builder = TreeBuilder()
    first = builder.initiative(100)
    second = builder.initiative(101)
    yield Steps(
        builder,
        builder.slice(first, 110),
        builder.slice(second, 111),
        first,
        second,
    )
    builder.close()


def test_no_planners_gives_no_actions() -> None:
    assert decide(_view(), ()) == []


def test_planners_concatenate_in_order(steps: Steps) -> None:
    first, second = _launch(steps.first.id), _launch(steps.second.id)

    actions = decide(steps.view(), (Fixed(first), Fixed(second)))

    assert actions == [first, second]


def test_two_actions_for_one_node_raise_and_name_it(steps: Steps) -> None:
    node_id = steps.first.id
    with pytest.raises(ValueError, match=f"node {node_id}"):
        decide(steps.view(), (Fixed(_launch(node_id)), Fixed(_launch(node_id))))


def test_two_actions_for_one_node_from_one_planner_raise(steps: Steps) -> None:
    node_id = steps.first.id
    with pytest.raises(ValueError, match=f"node {node_id}"):
        decide(steps.view(), (Fixed(_launch(node_id), _launch(node_id)),))


def test_decide_is_deterministic_and_hands_each_planner_the_same_view(
    steps: Steps,
) -> None:
    planner = Fixed(_launch(steps.first.id))
    view = steps.view()

    assert decide(view, (planner,)) == decide(view, (planner,))
    assert all(seen is view for seen in planner.views)


@pytest.mark.parametrize(
    "rows",
    [
        pytest.param((), id="nothing-driven"),
        pytest.param((row(drive=True, hold=True),), id="project-held"),
    ],
)
def test_an_action_on_a_ready_step_that_is_not_current_raises(
    steps: Steps, rows: tuple[DesiredState, ...]
) -> None:
    view = view_for(steps.builder.tree(), rows)
    everything = Fixed(*(_launch(n.id) for n in view.tree.ready_slices()))

    with pytest.raises(ValueError, match="not a current slice"):
        decide(view, (everything,))


def test_an_action_on_an_excluded_step_raises(steps: Steps) -> None:
    excluded = steps.view(row(drive=True), row(steps.first_owner, drive=False))
    with pytest.raises(ValueError, match=f"node {steps.first.id}"):
        decide(excluded, (Fixed(_launch(steps.first.id)),))


def test_a_planner_acting_only_on_current_slices_passes(steps: Steps) -> None:
    view = steps.view(row(drive=True), row(steps.second_owner, hold=True))
    action = _launch(steps.first.id)

    assert decide(view, (Fixed(action),)) == [action]
    with pytest.raises(ValueError, match=f"node {steps.second.id}"):
        decide(view, (Fixed(_launch(steps.second.id)),))


def test_an_action_naming_an_unknown_node_raises(steps: Steps) -> None:
    with pytest.raises(ValueError, match="node ghost"):
        decide(steps.view(), (Fixed(_launch("ghost")),))


def test_the_message_names_the_node_and_the_project(steps: Steps) -> None:
    with pytest.raises(ValueError, match="project demo"):
        decide(steps.view(), (Fixed(_launch("ghost")),))


def test_the_view_is_immutable() -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        _view().project_id = "other"  # type: ignore[misc]  # pyright: ignore[reportAttributeAccessIssue]


def test_a_driven_project_view_exposes_its_current_slices() -> None:
    builder = TreeBuilder()
    try:
        initiative = builder.initiative(100)
        architecture = builder.slice(initiative, 101)
        driven = view_for(builder.tree(), [row(drive=True)])
        assert list(driven.current_slices) == [architecture]
        assert driven.desired.drives_anything()
    finally:
        builder.close()


def test_a_view_with_no_rows_has_no_current_slices() -> None:
    builder = TreeBuilder()
    try:
        builder.initiative(100)
        undriven = view_for(builder.tree())
        assert list(undriven.current_slices) == []
        assert not undriven.desired.drives_anything()
    finally:
        builder.close()


def _block(node_id: str) -> BlockDispatch:
    return BlockDispatch(node_id, Block(FaultKind.CHECKOUT_DIRTY, "dirty", {}))


def test_a_block_for_a_current_step_passes(steps: Steps) -> None:
    action = _block(steps.first.id)

    assert decide(steps.view(), (Fixed(action),)) == [action]


def test_a_block_for_a_node_that_is_not_current_raises(steps: Steps) -> None:
    held = steps.view(row(drive=True), row(steps.first_owner, hold=True))

    with pytest.raises(ValueError, match=f"node {steps.first.id}"):
        decide(held, (Fixed(_block(steps.first.id)),))


def test_a_block_and_a_launch_for_one_node_raise(steps: Steps) -> None:
    node_id = steps.first.id

    with pytest.raises(ValueError, match=f"node {node_id}"):
        decide(steps.view(), (Fixed(_block(node_id)), Fixed(_launch(node_id))))


def test_a_reissuing_launch_carries_the_old_run_id_and_entry() -> None:
    action = LaunchRun("n", "P5", {}, Path("/w"), run_id="run-1", reissue_of="entry-1")

    assert (action.run_id, action.reissue_of) == ("run-1", "entry-1")
    assert _launch("n").run_id is None and _launch("n").reissue_of is None


def test_a_view_that_dispatches_nothing_has_empty_dispatch_facts() -> None:
    view = _view()

    assert view.dispatch == {}
    assert view.checkout_holders == {}


# -- slice 128, D5: nothing starts Squadron work unchecked -----------------------


def _resume(node_id: str) -> ResumeRun:
    return ResumeRun(
        node_id,
        "run-1",
        "entry-1",
        "b-1",
        Path("/w"),
        cause=ResumeCause.RESOLUTION,
    )


def test_decide_refuses_a_launch_without_a_passed_check(steps: Steps) -> None:
    view = replace(steps.view(), dispatch_checks={})

    with pytest.raises(ValueError, match="no passed pre-dispatch check"):
        decide(view, (Fixed(_launch(steps.first.id)),))


def test_decide_refuses_a_resume_without_a_passed_check(steps: Steps) -> None:
    view = replace(steps.view(), dispatch_checks={})

    with pytest.raises(ValueError, match="no passed pre-dispatch check"):
        decide(view, (Fixed(_resume(steps.first.id)),))


def test_decide_refuses_a_launch_whose_check_blocked(steps: Steps) -> None:
    block = Block(FaultKind.CHECKOUT_DIRTY, "dirty", {})
    view = replace(steps.view(), dispatch_checks={steps.first.id: block})

    with pytest.raises(ValueError, match="no passed pre-dispatch check"):
        decide(view, (Fixed(_launch(steps.first.id)),))


def test_a_block_dispatch_needs_no_check(steps: Steps) -> None:
    view = replace(steps.view(), dispatch_checks={})
    block = BlockDispatch(steps.first.id, Block(FaultKind.CHECKOUT_DIRTY, "dirty", {}))

    assert decide(view, (Fixed(block),)) == [block]


def test_a_resolution_resume_without_its_resolution_is_refused() -> None:
    with pytest.raises(ValueError, match="names the resolution"):
        ResumeRun(
            "n",
            "run-1",
            "entry-1",
            None,
            Path("/w"),
            cause=ResumeCause.RESOLUTION,
        )


def test_a_transient_resume_needs_no_resolution() -> None:
    resume = ResumeRun(
        "n",
        "run-1",
        "entry-1",
        None,
        Path("/w"),
        cause=ResumeCause.TRANSIENT,
    )

    assert resume.resolution is None and resume.instructions is None
