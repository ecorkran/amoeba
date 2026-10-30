"""``governing``: drive resolves from the nearest row, hold from any row (D4, D6)."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

import pytest

from amoeba.runner.intent.governance import (
    DesiredStateIndex,
    Governance,
    current_slices,
    governing,
)
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

    def govern(
        self, rows: list[DesiredState], slice_node: Node | None = None
    ) -> Governance:
        return governing(
            self.builder.tree(), DesiredStateIndex(rows), slice_node or self.first
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
    assert world.govern([]) == UNDRIVEN


def test_a_project_drive_drives_every_slice(world: World) -> None:
    rows = [row(drive=True)]
    assert world.govern(rows) == DRIVEN
    assert world.govern(rows, world.second) == DRIVEN


def test_an_initiative_exclude_undrives_its_slices_and_a_slice_drive_restores(
    world: World,
) -> None:
    rows = [row(drive=True), row(world.initiative, drive=False)]
    assert world.govern(rows) == UNDRIVEN

    rows.append(row(world.first, drive=True))
    assert world.govern(rows) == DRIVEN
    assert world.govern(rows, world.second) == UNDRIVEN


def test_project_pause_wins_over_a_slice_resume(world: World) -> None:
    # A slice "resume" removes the slice's own hold; it cannot lift the project's.
    rows = [row(drive=True, hold=True), row(world.first, drive=True)]
    assert world.govern(rows) == DRIVEN_HELD


def test_no_project_pause_leaves_the_slice_unheld(world: World) -> None:
    rows = [row(drive=True), row(world.first, drive=True)]
    assert world.govern(rows).held is False


def test_a_slice_pause_does_not_hold_its_sibling(world: World) -> None:
    rows = [row(drive=True), row(world.first, hold=True)]
    assert world.govern(rows).held is True
    assert world.govern(rows, world.second).held is False


def test_a_hold_only_row_does_not_decide_drive(world: World) -> None:
    rows = [row(drive=True), row(world.first, hold=True)]
    assert world.govern(rows) == DRIVEN_HELD
    assert world.govern([row(world.first, hold=True)]) == HELD_UNDRIVEN


def test_a_stored_drive_until_step_is_ignored(world: World) -> None:
    """Rows written before slice 132 may still carry one; it no longer limits work."""
    rows = [row(world.first, drive=True, until="tasks")]

    assert world.govern(rows).driven is True


def test_governing_a_node_that_is_not_a_slice_raises(world: World) -> None:
    with pytest.raises(ValueError, match="not a slice"):
        governing(world.builder.tree(), DesiredStateIndex([]), world.initiative)


def _current(world: World, rows: list[DesiredState]) -> list[Node]:
    return list(current_slices(world.builder.tree(), DesiredStateIndex(rows)))


def test_only_ready_slices_can_be_current(world: World) -> None:
    current = _current(world, [row(drive=True)])
    ready = list(world.builder.tree().ready_slices())
    assert current == ready == [world.first], "the second waits for the first"


def test_a_driven_unheld_ready_slice_is_current(world: World) -> None:
    assert world.first in _current(world, [row(drive=True)])


def test_held_and_undriven_ready_slices_are_not_current(world: World) -> None:
    plain = world.builder.slice(world.builder.initiative(150), 151)
    rows = [
        row(drive=True),
        row(world.first, hold=True),
        row(world.second, drive=False),
    ]

    assert _current(world, rows) == [plain]


def test_nothing_is_current_without_a_drive(world: World) -> None:
    assert _current(world, [row(world.first, hold=True)]) == []


def test_an_orphans_row_never_affects_a_current_slice(world: World) -> None:
    orphan = world.builder.slice(world.initiative, 143)
    world.builder.orphan(orphan)
    baseline = _current(world, [row(drive=True)])
    with_orphan_row = _current(
        world, [row(drive=True), row(orphan, drive=False, hold=True)]
    )
    assert with_orphan_row == baseline
    assert orphan not in with_orphan_row


def test_current_slices_keep_ready_slices_order(world: World) -> None:
    current = _current(world, [row(drive=True)])
    ready = [node.id for node in world.builder.tree().ready_slices()]
    assert [node.id for node in current] == ready
