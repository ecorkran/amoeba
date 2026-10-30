"""``governing``: drive resolves from the nearest row, hold from any row (D4, D6)."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

import pytest

from amoeba.runner.intent.governance import (
    DesiredStateIndex,
    Governance,
    current_steps,
    governing,
)
from amoeba.runner.lifecycle.steps import LifecycleStep
from amoeba.store import DesiredState, Node
from runner.lifecycle.tree_support import TreeBuilder

from .rows_support import row

UNDRIVEN = Governance(driven=False, held=False)
DRIVEN = Governance(driven=True, held=False)
HELD_UNDRIVEN = Governance(driven=False, held=True)
DRIVEN_HELD = Governance(driven=True, held=True)


@dataclass
class World:
    builder: TreeBuilder
    initiative: Node
    first: Node  # a slice of the initiative
    second: Node  # its sibling

    def at(self, step: LifecycleStep, owner: Node | None = None) -> Node:
        return self.builder.step_node(owner or self.first, step)

    def govern(
        self, rows: list[DesiredState], step: LifecycleStep, owner: Node | None = None
    ) -> Governance:
        return governing(
            self.builder.tree(), DesiredStateIndex(rows), self.at(step, owner)
        )


@pytest.fixture
def world() -> Iterator[World]:
    builder = TreeBuilder()
    initiative = builder.initiative(140)
    yield World(
        builder,
        initiative,
        builder.slice(initiative, 141),
        builder.slice(initiative, 142),
    )
    builder.close()


def test_nothing_is_driven_by_default(world: World) -> None:
    for step in LifecycleStep:
        owner = world.initiative if step in _INITIATIVE_STEPS else None
        assert world.govern([], step, owner) == UNDRIVEN


_INITIATIVE_STEPS = {
    LifecycleStep.ARCHITECTURE,
    LifecycleStep.SLICE_PLAN,
    LifecycleStep.INTEGRATION,
}


def test_a_project_drive_drives_every_step(world: World) -> None:
    rows = [row(drive=True)]
    assert world.govern(rows, LifecycleStep.ARCHITECTURE, world.initiative) == DRIVEN
    assert world.govern(rows, LifecycleStep.TASKS) == DRIVEN


def test_an_initiative_exclude_undrives_its_steps_and_a_slice_drive_restores(
    world: World,
) -> None:
    rows = [row(drive=True), row(world.initiative, drive=False)]
    assert world.govern(rows, LifecycleStep.SLICE_PLAN, world.initiative) == UNDRIVEN
    assert world.govern(rows, LifecycleStep.TASKS) == UNDRIVEN

    rows.append(row(world.first, drive=True))
    assert world.govern(rows, LifecycleStep.TASKS) == DRIVEN
    assert world.govern(rows, LifecycleStep.TASKS, world.second) == UNDRIVEN


def test_project_pause_wins_over_a_slice_resume(world: World) -> None:
    # A slice "resume" removes the slice's own hold; it cannot lift the project's.
    rows = [row(drive=True, hold=True), row(world.first, drive=True)]
    assert world.govern(rows, LifecycleStep.TASKS) == DRIVEN_HELD


def test_no_project_pause_leaves_the_slice_unheld(world: World) -> None:
    rows = [row(drive=True), row(world.first, drive=True)]
    assert world.govern(rows, LifecycleStep.TASKS).held is False


def test_a_slice_pause_does_not_hold_its_sibling(world: World) -> None:
    rows = [row(drive=True), row(world.first, hold=True)]
    assert world.govern(rows, LifecycleStep.TASKS).held is True
    assert world.govern(rows, LifecycleStep.TASKS, world.second).held is False


def test_a_hold_only_row_does_not_decide_drive(world: World) -> None:
    rows = [row(drive=True), row(world.first, hold=True)]
    assert world.govern(rows, LifecycleStep.TASKS) == DRIVEN_HELD
    assert world.govern([row(world.first, hold=True)], LifecycleStep.TASKS) == (
        HELD_UNDRIVEN
    )


def test_a_stored_drive_until_step_is_ignored(world: World) -> None:
    """Rows written before slice 132 may still carry one; it no longer limits work."""
    rows = [row(world.first, drive=True, until=LifecycleStep.TASKS.value)]

    assert world.govern(rows, LifecycleStep.TASKS).driven is True
    assert world.govern(rows, LifecycleStep.IMPLEMENTATION).driven is True


def test_governing_a_node_that_is_not_a_step_raises(world: World) -> None:
    with pytest.raises(ValueError, match="not a step"):
        governing(world.builder.tree(), DesiredStateIndex([]), world.first)


def _finish_planning(world: World) -> None:
    """Done architecture and slice plan, so both slices' design steps are ready."""
    for step in (LifecycleStep.ARCHITECTURE, LifecycleStep.SLICE_PLAN):
        world.builder.done(world.at(step, world.initiative))


def _current(world: World, rows: list[DesiredState]) -> list[Node]:
    return list(current_steps(world.builder.tree(), DesiredStateIndex(rows)))


def test_only_ready_steps_can_be_current(world: World) -> None:
    current = _current(world, [row(drive=True)])
    ready = list(world.builder.tree().ready_steps())
    assert current == ready
    assert world.at(LifecycleStep.IMPLEMENTATION) not in current


def test_a_driven_unheld_ready_step_is_current(world: World) -> None:
    _finish_planning(world)
    assert world.at(LifecycleStep.SLICE_DESIGN) in _current(world, [row(drive=True)])


def test_held_and_undriven_ready_steps_are_not_current(world: World) -> None:
    _finish_planning(world)
    rows = [
        row(drive=True),
        row(world.first, hold=True),
        row(world.second, drive=False),
    ]
    plain = world.builder.slice(world.initiative, 143)
    current = _current(world, rows)
    assert current == [world.at(LifecycleStep.SLICE_DESIGN, plain)]


def test_nothing_is_current_without_a_drive(world: World) -> None:
    assert _current(world, [row(world.first, hold=True)]) == []


def test_an_orphans_row_never_affects_a_current_step(world: World) -> None:
    _finish_planning(world)
    orphan = world.builder.slice(world.initiative, 143)
    world.builder.orphan(orphan)
    baseline = _current(world, [row(drive=True)])
    with_orphan_row = _current(
        world, [row(drive=True), row(orphan, drive=False, hold=True)]
    )
    assert with_orphan_row == baseline
    assert world.at(LifecycleStep.SLICE_DESIGN, orphan) not in with_orphan_row


def test_current_steps_keep_ready_steps_order(world: World) -> None:
    _finish_planning(world)
    current = _current(world, [row(drive=True)])
    ready = [node.id for node in world.builder.tree().ready_steps()]
    assert [node.id for node in current] == ready
