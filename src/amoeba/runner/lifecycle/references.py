"""The update rule: keep a linked node's CF references equal to CF's (D2, D5 step 3).

A rename or a changed design file updates ``slice_name`` and ``artifact_path`` on
the same node: its id and link are unchanged, so earlier reviews stay attributed to
it and later ones attribute under the new slug. Titles are display data and are
never updated (issue #11).

CF supplying no value (no ``archFile``, no ``designFile``) is "no information", not
a change: the existing value stays. A slice's ``slice_name`` is set from CF's design
file here, and by slice 125 from the pointer it reads back before launching a design
run; clearing it because the list has no design file yet would undo that.
"""

from __future__ import annotations

import dataclasses
import logging

from amoeba.runner.lifecycle.plan_read import PlanRead
from amoeba.runner.lifecycle.read_checks import ReadScope
from amoeba.runner.lifecycle.slugs import slice_name_from_design_file
from amoeba.runner.lifecycle.tree import LifecycleTree
from amoeba.store import Node, NodeKind, Store
from amoeba.upstream.context_forge import CFSliceList

logger = logging.getLogger(__name__)


def update_references(
    store: Store,
    tree: LifecycleTree,
    cf_project_id: str,
    read: PlanRead,
    scope: ReadScope,
) -> bool:
    """Update each linked node whose design or architecture file CF changed.

    Returns:
        Whether anything was written.
    """
    wrote = False
    for initiative in read.initiatives:
        node = tree.find_linked(NodeKind.INITIATIVE, cf_project_id, initiative.index)
        if node and initiative.arch_file:
            wrote = _set(store, node, artifact_path=initiative.arch_file) or wrote

    for initiative_index in sorted(scope.slice_initiatives):
        slices = read.slices[initiative_index]
        if not isinstance(slices, CFSliceList):
            continue
        for entry in slices.entries:
            node = tree.find_linked(NodeKind.SLICE, cf_project_id, entry.index)
            if node and entry.design_file:
                name = slice_name_from_design_file(entry.design_file)
                wrote = _set_slice(store, node, entry.design_file, name) or wrote
    return wrote


def _set_slice(store: Store, node: Node, design_file: str, name: str | None) -> bool:
    if name is None and node.cf.artifact_path != design_file:
        logger.warning(
            "slice %s design file %r is not in the nnn-slice.{name}.md form; "
            "keeping slice_name %r",
            node.cf.index,
            design_file,
            node.cf.slice_name,
        )
    return _set(
        store,
        node,
        artifact_path=design_file,
        slice_name=name if name is not None else node.cf.slice_name,
    )


def _set(
    store: Store,
    node: Node,
    *,
    artifact_path: str,
    slice_name: str | None = None,
) -> bool:
    """Write the new references if they differ; replace only those two fields."""
    desired_name = slice_name if slice_name is not None else node.cf.slice_name
    if node.cf.artifact_path == artifact_path and node.cf.slice_name == desired_name:
        return False
    store.update_cf_reference(
        node.id,
        dataclasses.replace(
            node.cf, artifact_path=artifact_path, slice_name=desired_name
        ),
    )
    return True
