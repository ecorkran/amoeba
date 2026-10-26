"""A slice whose implementation just finished, for the merge-observation tests."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from amoeba.process import RunOutcome
from amoeba.runner.cf_call import CfRun
from amoeba.runner.lifecycle.steps import LifecycleStep
from amoeba.store import CFReference, Node, NodeKind, NodeStatus
from runner.dispatch.tick_rig import DispatchRig
from runner.gate_rig import clear_gates
from runner.git_repo import commit_file, head_of, make_branch, merge_branch, switch
from runner.resolutions.rig_support import INDEX, write_review

PROJECT = "demo"
BRANCH = f"{INDEX}-slice.merge-me"


@dataclass
class Scenario:
    """A slice whose implementation just finished, and its merge step."""

    slice_node: Node
    implementation: Node
    merge: Node
    head: str


def implemented(
    rig: DispatchRig,
    *,
    own_branch: bool = True,
    auto_merged: bool = False,
    wrap_gate_run: Callable[[CfRun], CfRun] | None = None,
) -> Scenario:
    """Run ``P6`` to completion, leaving the checkout as Squadron would.

    Under ``human`` the run ends on the slice's own branch with its work committed.
    ``own_branch=False`` ends it on the target; ``auto_merged`` has Squadron merge the
    slice branch into the target before it completes.
    """
    root = rig.world.root
    slice_node, implementation = rig.slice_and_step(
        "merge-me", INDEX, LifecycleStep.IMPLEMENTATION
    )
    merge = rig.store.create_node(
        project_id=PROJECT,
        kind=NodeKind.PHASE_OR_ARTIFACT,
        title=LifecycleStep.MERGE.value,
        parent_id=slice_node.id,
        cf=CFReference(project="cf-a", phase=LifecycleStep.MERGE.value),
    )
    clear_gates(rig, slice_node, LifecycleStep.IMPLEMENTATION)
    if wrap_gate_run is not None:
        rig.tick_rig.gate_run = wrap_gate_run(rig.tick_rig.gate_run)
    rig.tick()  # the pointer write
    rig.tick()  # the launch, on the target
    if own_branch or auto_merged:
        make_branch(root, BRANCH)
        commit_file(root, "work.txt", "slice work\n", "implement the slice")
    if auto_merged:
        switch(root, "main")
        merge_branch(root, BRANCH)
    head = head_of(root)
    rig.end_run(
        implementation,
        RunOutcome.COMPLETED,
        **write_review(rig, "verdict: PASS").document,
    )
    assert rig.status(implementation) is NodeStatus.DONE
    return Scenario(slice_node, implementation, merge, head)
