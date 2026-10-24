"""Human steps in the project tick, with the planner in a test tuple."""

from __future__ import annotations

from pathlib import Path

import pytest

from amoeba.runner.lifecycle.human_steps import HumanStepPlanner
from amoeba.runner.lifecycle.steps import LifecycleStep
from amoeba.store import Node, NodeKind, NodeStatus, Store
from amoeba.store.inbox_models import Channel
from runner.observe_support import CfReply
from runner.plan_tick_support import (
    INITIATIVES_KEY,
    initiatives_json,
    serve_plan,
    slices_key,
)
from runner.tick_support import PLAN_READ_INTERVAL, PROJECT, Rig, link

LINK = "cf-1"


@pytest.fixture
def rig(tmp_path: Path, store: Store) -> Rig:
    built = Rig(tmp_path, store)
    built.planners = (HumanStepPlanner(),)
    link(store, "s-1", LINK, PROJECT)
    return built


def _step(store: Store, kind: NodeKind, index: int, step: LifecycleStep) -> Node:
    [owner] = [
        n
        for n in store.nodes_for_project(PROJECT)
        if n.kind is kind and n.cf.index == index
    ]
    [found] = [c for c in store.children_of(owner.id) if c.cf.phase == step.value]
    return found


def _status(store: Store, node: Node) -> NodeStatus:
    current = store.get_node(node.id)
    assert current is not None
    return current.status


def _no_arch(rig: Rig) -> None:
    rig.cf.replies[INITIATIVES_KEY] = CfReply(initiatives_json(140, arch_file=None))
    rig.cf.replies[slices_key(140)] = CfReply("", 1, '{"error":true,"code":"UNKNOWN"}')


def test_architecture_without_an_arch_file_is_blocked_with_its_payload(
    rig: Rig, store: Store
) -> None:
    _no_arch(rig)

    rig.tick()

    step = _step(store, NodeKind.INITIATIVE, 140, LifecycleStep.ARCHITECTURE)
    assert _status(store, step) is NodeStatus.BLOCKED_ON_HUMAN
    [message] = [
        m
        for m in store.messages(PROJECT, channel=Channel.ESCALATION)
        if m.node_id == step.id
    ]
    assert message.payload == {
        "step": "architecture",
        "cf_project_id": LINK,
        "index": 140,
    }
    assert rig.popen.calls == 0
    assert store.unresolved_journal_entries(PROJECT) == []


def test_merge_is_blocked_after_implementation_is_done(rig: Rig, store: Store) -> None:
    serve_plan(rig.cf, (100,), {100: (101,)})
    rig.tick()
    for step in (
        LifecycleStep.SLICE_DESIGN,
        LifecycleStep.TASKS,
        LifecycleStep.IMPLEMENTATION,
    ):
        store.update_node_status(
            _step(store, NodeKind.SLICE, 101, step).id, NodeStatus.DONE
        )

    rig.tick()

    merge = _step(store, NodeKind.SLICE, 101, LifecycleStep.MERGE)
    assert _status(store, merge) is NodeStatus.BLOCKED_ON_HUMAN


def test_when_the_predicate_becomes_true_the_next_read_resolves_the_block(
    rig: Rig, store: Store
) -> None:
    _no_arch(rig)
    rig.tick()
    step = _step(store, NodeKind.INITIATIVE, 140, LifecycleStep.ARCHITECTURE)
    rig.cf.replies[INITIATIVES_KEY] = CfReply(initiatives_json(140))

    rig.clock.seconds = PLAN_READ_INTERVAL
    rig.tick()

    assert _status(store, step) is NodeStatus.DONE
    [state] = list(store.all_blocked_states(step.id))
    assert state.resolution is not None and state.resolution.resolved_by == "runner"


def test_a_person_resolving_without_doing_the_work_is_blocked_again(
    rig: Rig, store: Store
) -> None:
    _no_arch(rig)
    rig.tick()
    step = _step(store, NodeKind.INITIATIVE, 140, LifecycleStep.ARCHITECTURE)
    store.resolve(step.id, resolved_by="pm", detail="not yet")
    assert _status(store, step) is NodeStatus.RUNNABLE

    rig.clock.seconds = 1.0
    rig.tick()

    assert _status(store, step) is NodeStatus.BLOCKED_ON_HUMAN
    assert len(list(store.all_blocked_states(step.id))) == 2
