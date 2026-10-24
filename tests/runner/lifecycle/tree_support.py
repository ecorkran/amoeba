"""Build lifecycle trees through a real in-memory store, for pure tree tests."""

from __future__ import annotations

from amoeba.runner.lifecycle.steps import STEP_MAP, LifecycleStep, StepLevel
from amoeba.runner.lifecycle.tree import LifecycleTree
from amoeba.store import Store
from amoeba.store.models import (
    BlockedKind,
    CFReference,
    Node,
    NodeKind,
    NodeStatus,
)

PROJECT = "demo"
CF_PROJECT = "cf-a"


class TreeBuilder:
    """Creates linked initiatives, slices and steps, then the tree over them."""

    def __init__(self, project_id: str = PROJECT) -> None:
        self.store = Store.open_temporary()
        self.project_id = project_id

    def close(self) -> None:
        self.store.close()

    def initiative(self, index: int, *, cf_project: str = CF_PROJECT) -> Node:
        """A linked initiative with its three initiative-level steps."""
        node = self.store.create_node(
            project_id=self.project_id,
            kind=NodeKind.INITIATIVE,
            title=f"initiative {index}",
            cf=CFReference(project=cf_project, index=index),
        )
        self.steps(node, StepLevel.INITIATIVE)
        return node

    def slice(self, parent: Node, index: int, *, with_steps: bool = True) -> Node:
        """A linked slice under ``parent``, with its four steps unless asked not to."""
        node = self.store.create_node(
            project_id=self.project_id,
            kind=NodeKind.SLICE,
            title=f"slice {index}",
            parent_id=parent.id,
            cf=CFReference(project=parent.cf.project, index=index),
        )
        if with_steps:
            self.steps(node, StepLevel.SLICE)
        return node

    def steps(self, parent: Node, level: StepLevel) -> None:
        for step in (s for s, spec in STEP_MAP.items() if spec.level is level):
            self.step(parent, step)

    def step(self, parent: Node, step: LifecycleStep) -> Node:
        return self.store.create_node(
            project_id=self.project_id,
            kind=NodeKind.PHASE_OR_ARTIFACT,
            title=step.value,
            parent_id=parent.id,
            cf=CFReference(project=parent.cf.project, phase=step.value),
        )

    def step_node(self, parent: Node, step: LifecycleStep) -> Node:
        """The existing step child of ``parent``, read back from the store."""
        for child in self.store.children_of(parent.id):
            if child.cf.phase == step.value:
                return child
        raise LookupError(f"{parent.title} has no {step.value} step")

    def fresh(self, node: Node) -> Node:
        """The node as the store holds it now (nodes are immutable snapshots)."""
        current = self.store.get_node(node.id)
        if current is None:
            raise LookupError(f"node {node.id} vanished")
        return current

    def done(self, node: Node) -> None:
        self.store.update_node_status(node.id, NodeStatus.DONE)

    def block(self, node: Node) -> None:
        self.store.block(node.id, kind=BlockedKind.HUMAN, context="blocked in a test")

    def orphan(self, node: Node) -> None:
        """Clear the node's CF index, as reconcile's orphan rule does."""
        self.store.update_cf_reference(
            node.id,
            CFReference(project=node.cf.project, phase=node.cf.phase, index=None),
        )

    def tree(self) -> LifecycleTree:
        return LifecycleTree(self.store.nodes_for_project(self.project_id))
