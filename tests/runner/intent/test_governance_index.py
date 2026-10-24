"""``DesiredStateIndex``: lookup by target, and ``drives_anything``."""

from __future__ import annotations

from amoeba.runner.intent.governance import DesiredStateIndex
from amoeba.store import Node, NodeKind, NodeStatus

from .rows_support import row

NODE = Node(
    id="n-1",
    project_id="demo",
    kind=NodeKind.SLICE,
    status=NodeStatus.RUNNABLE,
    title="n",
)


def test_lookup_finds_the_project_row_and_a_node_row() -> None:
    project_row = row(drive=True)
    node_row = row(NODE, hold=True)
    index = DesiredStateIndex([project_row, node_row])

    assert index.row_for(None) is project_row
    assert index.row_for(NODE.id) is node_row


def test_lookup_of_a_missing_target_is_none() -> None:
    index = DesiredStateIndex([row(drive=True)])
    assert index.row_for("missing") is None
    assert DesiredStateIndex([]).row_for(None) is None


def test_drives_anything() -> None:
    assert not DesiredStateIndex([]).drives_anything()
    assert not DesiredStateIndex([row(drive=False)]).drives_anything()
    assert not DesiredStateIndex(
        [row(hold=True), row(NODE, hold=True)]
    ).drives_anything()
    assert DesiredStateIndex([row(hold=True), row(NODE, drive=True)]).drives_anything()
