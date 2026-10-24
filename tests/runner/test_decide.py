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
    InFlightRun,
    LaunchRun,
    ProjectView,
    RunState,
    decide,
)
from amoeba.runner.lifecycle.steps import LifecycleStep
from amoeba.runner.lifecycle.tree import LifecycleTree
from amoeba.store import DesiredState, Node
from runner.intent.rows_support import row
from runner.lifecycle.tree_support import TreeBuilder
from runner.observe_support import entry
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
    """Two initiatives' ready architecture steps, with the project driven."""

    builder: TreeBuilder
    first: Node
    second: Node
    first_owner: Node
    second_owner: Node

    def view(self, *rows: DesiredState) -> ProjectView:
        return view_for(self.builder.tree(), rows or (row(drive=True),))


@pytest.fixture
def steps() -> Iterator[Steps]:
    builder = TreeBuilder()
    first = builder.initiative(100)
    second = builder.initiative(101)
    yield Steps(
        builder,
        builder.step_node(first, LifecycleStep.ARCHITECTURE),
        builder.step_node(second, LifecycleStep.ARCHITECTURE),
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
    everything = Fixed(*(_launch(n.id) for n in view.tree.ready_steps()))

    with pytest.raises(ValueError, match="not a current step"):
        decide(view, (everything,))


def test_an_action_on_an_excluded_step_raises(steps: Steps) -> None:
    excluded = steps.view(row(drive=True), row(steps.first_owner, drive=False))
    with pytest.raises(ValueError, match=f"node {steps.first.id}"):
        decide(excluded, (Fixed(_launch(steps.first.id)),))


def test_a_planner_acting_only_on_current_steps_passes(steps: Steps) -> None:
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


def test_ready_unbusy_offers_only_ready_steps_without_a_run_in_flight() -> None:
    builder = TreeBuilder()
    try:
        initiative = builder.initiative(100)
        architecture = builder.step_node(initiative, LifecycleStep.ARCHITECTURE)
        view = view_for(builder.tree())
        assert view.ready_unbusy() == [architecture], "no containers, no blocked steps"

        running = InFlightRun(
            replace(entry(), node_id=architecture.id), "run-1", RunState.RUNNING
        )
        busy = replace(view, in_flight=(running,))
        assert busy.ready_unbusy() == []
    finally:
        builder.close()


def test_a_driven_project_view_exposes_its_current_steps() -> None:
    builder = TreeBuilder()
    try:
        initiative = builder.initiative(100)
        architecture = builder.step_node(initiative, LifecycleStep.ARCHITECTURE)
        driven = view_for(builder.tree(), [row(drive=True)])
        assert list(driven.current_steps) == [architecture]
        assert driven.desired.drives_anything()
    finally:
        builder.close()


def test_a_view_with_no_rows_has_no_current_steps() -> None:
    builder = TreeBuilder()
    try:
        builder.initiative(100)
        undriven = view_for(builder.tree())
        assert list(undriven.current_steps) == []
        assert not undriven.desired.drives_anything()
    finally:
        builder.close()
