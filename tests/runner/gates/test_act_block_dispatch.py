"""D5: ``BlockDispatch`` is a store-only block, written once."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from amoeba.runner.act import ActStage
from amoeba.runner.budget import TickBudget, TickResult
from amoeba.runner.decide import BlockDispatch
from amoeba.runner.faults import PAYLOAD_FAULT_KIND, FaultKind, TickFaults
from amoeba.runner.gates.predispatch import Block
from amoeba.store import BlockedKind, Channel, Node, Store
from runner.observe_support import Host
from runner.tick_support import PROJECT, Rig, ready_step


@pytest.fixture
def rig(tmp_path: Path, store: Store) -> Iterator[Rig]:
    yield Rig(tmp_path, store)


def _act(rig: Rig) -> ActStage:
    return ActStage(
        store=rig.store,
        supervisor_dir=rig.supervisor_dir,
        pointers=rig.pointers,
        poll_run=rig.observer.poll_run,
        tracker=rig.tracker,
        popen=rig.popen,
        now=rig.clock.wall,
        context=rig.context,
        version_label="sq-test-label",
    )


def _budget(rig: Rig) -> TickBudget:
    return TickBudget(rig.deadline, Host(), rig.clock.monotonic)


def _dirty(node: Node, context: str = "the tree is dirty") -> BlockDispatch:
    block = Block(FaultKind.CHECKOUT_DIRTY, context, {"paths": ["a.txt"], "count": 1})
    return BlockDispatch(node.id, block)


def test_a_block_dispatch_writes_one_block_and_no_journal_entry(rig: Rig) -> None:
    node = ready_step(rig.store)

    outcome = _act(rig).run([_dirty(node)], budget=_budget(rig), faults=TickFaults())

    assert outcome.result is TickResult.COMPLETE and outcome.wrote
    [state] = rig.store.all_blocked_states(node.id)
    assert state.kind is BlockedKind.HUMAN
    assert state.context == "the tree is dirty"
    [message] = rig.store.messages(PROJECT, channel=Channel.ESCALATION)
    assert message.payload == {
        "paths": ["a.txt"],
        "count": 1,
        PAYLOAD_FAULT_KIND: "checkout_dirty",
    }
    assert rig.store.journal_entries(PROJECT) == []


def test_a_second_block_dispatch_for_a_blocked_step_is_skipped(rig: Rig) -> None:
    node = ready_step(rig.store)
    act = _act(rig)

    act.run([_dirty(node)], budget=_budget(rig), faults=TickFaults())
    act.run([_dirty(node, "again")], budget=_budget(rig), faults=TickFaults())

    [state] = rig.store.all_blocked_states(node.id)
    assert state.context == "the tree is dirty"
