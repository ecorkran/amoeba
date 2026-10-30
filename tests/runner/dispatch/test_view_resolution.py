"""The dispatch facts carry an applied resolution and the run it continues (D5)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from amoeba.process import RunOutcome
from amoeba.runner.dispatch.build_view import DispatchView, build_dispatch_view
from amoeba.runner.dispatch.state import DispatchState
from amoeba.runner.faults import NodeContext
from amoeba.runner.lifecycle.tree import LifecycleTree
from amoeba.runner.resolutions.stage import apply_pending_resolutions
from amoeba.store import CommandKind, Node, Store
from runner.dispatch.tick_rig import PROJECT, DispatchRig
from runner.resolutions.resolution_support import (
    block_and_resolve,
    finished_run,
    paused_document,
)


@pytest.fixture
def rig(tmp_path: Path, store: Store) -> Iterator[DispatchRig]:
    yield DispatchRig(tmp_path, store)


def _view(rig: DispatchRig, node: Node) -> DispatchView:
    tree = LifecycleTree(rig.store.nodes_for_project(PROJECT))
    return build_dispatch_view(
        rig.store, PROJECT, tree, [node], frozenset(), is_dir=Path.is_dir
    )


def _answered(
    rig: DispatchRig,
    decision: str,
    node: Node,
    outcome: RunOutcome = RunOutcome.PAUSED,
) -> str:
    """A run in the world's checkout, resolved with ``decision`` and answered."""
    finished_run(
        rig.store,
        node,
        outcome,
        document=paused_document("run-x") if outcome is RunOutcome.PAUSED else None,
        checkout=str(rig.world.root),
    )
    blocked_id = block_and_resolve(rig.store, node, decision)
    apply_pending_resolutions(rig.store, PROJECT, NodeContext())
    return blocked_id


def test_an_applied_retry_is_resume_with_the_continued_entry(
    rig: DispatchRig,
) -> None:
    node = rig.step("resumable", 150)
    blocked_id = _answered(rig, "resume", node)
    [paused] = rig.entries(CommandKind.SQ_RUN, node)

    facts = _view(rig, node).facts[node.id]

    assert facts.state is DispatchState.RESUME
    assert facts.continues is not None and facts.continues.id == paused.id
    assert facts.resolution is not None and facts.resolution.id == blocked_id


def test_a_resume_with_no_run_needs_a_pointer_and_continues_nothing(
    rig: DispatchRig,
) -> None:
    node = rig.step("rerun", 150)
    _answered(rig, "resume", node, RunOutcome.COMPLETED)
    facts = _view(rig, node).facts[node.id]

    assert facts.state is DispatchState.NEEDS_POINTER
    assert facts.continues is None
    assert facts.resolution is not None


def test_a_paused_runs_checkout_is_held_by_its_own_node(rig: DispatchRig) -> None:
    node = rig.step("holder", 150)
    _answered(rig, "resume", node)

    view = _view(rig, node)

    assert view.holders[rig.world.root] == {node.id}
