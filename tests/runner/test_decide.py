"""The decide stage is pure, ordered and refuses two actions for one node."""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

import pytest

from amoeba.runner.decide import Action, LaunchRun, ProjectView, decide

NOW = datetime(2026, 10, 23, tzinfo=UTC)


def _view() -> ProjectView:
    return ProjectView("demo", NOW, (), (), {})


def _launch(node_id: str) -> LaunchRun:
    return LaunchRun(node_id, "noop", {"k": "v"}, Path("/work"))


class Fixed:
    def __init__(self, *actions: Action) -> None:
        self._actions = actions
        self.views: list[ProjectView] = []

    def plan(self, view: ProjectView) -> Sequence[Action]:
        self.views.append(view)
        return self._actions


def test_no_planners_gives_no_actions() -> None:
    assert decide(_view(), ()) == []


def test_planners_concatenate_in_order() -> None:
    first, second = _launch("a"), _launch("b")

    actions = decide(_view(), (Fixed(first), Fixed(second)))

    assert actions == [first, second]


def test_two_actions_for_one_node_raise_and_name_it() -> None:
    with pytest.raises(ValueError, match="node a"):
        decide(_view(), (Fixed(_launch("a")), Fixed(_launch("a"))))


def test_two_actions_for_one_node_from_one_planner_raise() -> None:
    with pytest.raises(ValueError, match="node a"):
        decide(_view(), (Fixed(_launch("a"), _launch("a")),))


def test_decide_is_deterministic_and_hands_each_planner_the_same_view() -> None:
    planner = Fixed(_launch("a"))
    view = _view()

    assert decide(view, (planner,)) == decide(view, (planner,))
    assert all(seen is view for seen in planner.views)


def test_the_view_is_immutable() -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        _view().project_id = "other"  # type: ignore[misc]  # pyright: ignore[reportAttributeAccessIssue]
