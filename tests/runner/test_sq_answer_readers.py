"""D3: an answerer run (``sq_answer``) is invisible to the slice's command readers.

One slice journal: a paused ``sq_run``, plus an ``sq_answer`` that is in flight or
resolved. Each reader has its own assertion, so a missing filter in any one reader
fails a test that names it.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from amoeba.process import RunOutcome, RunOutcomeDocument
from amoeba.runner.dispatch.build_view import DispatchView, build_dispatch_view
from amoeba.runner.dispatch.hold import checkout_holders
from amoeba.runner.dispatch.state import DispatchState
from amoeba.runner.faults import NodeContext
from amoeba.runner.ingest.record import (
    _resume_count,  # pyright: ignore[reportPrivateUsage]
)
from amoeba.runner.lifecycle.tree import LifecycleTree
from amoeba.runner.observed import RunEnded
from amoeba.runner.resolutions.stage import apply_pending_resolutions
from amoeba.runner.supervise import run_to_resume
from amoeba.store import (
    CommandKind,
    JournalEntry,
    JournalOutcome,
    Node,
    ResolutionOutcome,
    Store,
    supervision_entries,
)
from runner.dispatch.tick_rig import PROJECT, DispatchRig
from runner.resolutions.resolution_support import (
    block_and_resolve,
    finished_run,
    paused_document,
)

ANSWER_RUN_ID = "run-answer-0001"


@pytest.fixture
def rig(tmp_path: Path, store: Store) -> Iterator[DispatchRig]:
    yield DispatchRig(tmp_path, store)


def _journal_answer(store: Store, node: Node, *, resolved: bool) -> JournalEntry:
    entry = store.journal_issue(
        node.id,
        kind=CommandKind.SQ_ANSWER,
        parameters={
            "run_id": ANSWER_RUN_ID,
            "pipeline": "answering.yaml",
            "params": {},
            "scratch": "/tmp/answering/scratch",
        },
    )
    if resolved:
        return store.journal_resolve(entry.id, outcome=JournalOutcome.COMPLETED)
    return entry


def _paused_slice(rig: DispatchRig, *, answer_resolved: bool) -> Node:
    """A slice with a paused run and an ``sq_answer`` journaled after it."""
    node = rig.step("answerable", 150)
    finished_run(
        rig.store,
        node,
        RunOutcome.PAUSED,
        document=paused_document("run-x"),
        checkout=str(rig.world.root),
    )
    _journal_answer(rig.store, node, resolved=answer_resolved)
    return node


def _view(rig: DispatchRig, node: Node) -> DispatchView:
    tree = LifecycleTree(rig.store.nodes_for_project(PROJECT))
    return build_dispatch_view(rig.store, PROJECT, tree, [node], is_dir=Path.is_dir)


@pytest.mark.parametrize("answer_resolved", [False, True])
def test_classify_sees_the_paused_run_to_resume(
    rig: DispatchRig, answer_resolved: bool
) -> None:
    node = _paused_slice(rig, answer_resolved=answer_resolved)
    blocked_id = block_and_resolve(rig.store, node, "resume")

    apply_pending_resolutions(rig.store, PROJECT, NodeContext())

    blocked = rig.store.blocked_state(blocked_id)
    assert blocked is not None
    assert blocked.runner_outcome is ResolutionOutcome.APPLIED


@pytest.mark.parametrize("answer_resolved", [False, True])
def test_run_to_resume_returns_the_sq_run(
    rig: DispatchRig, answer_resolved: bool
) -> None:
    node = _paused_slice(rig, answer_resolved=answer_resolved)
    entries = rig.store.journal_entries(PROJECT, node_id=node.id)
    [paused] = rig.entries(CommandKind.SQ_RUN, node)

    found = run_to_resume(entries)

    assert found is not None and found.id == paused.id


@pytest.mark.parametrize("answer_resolved", [False, True])
def test_the_dispatch_facts_resume_the_paused_run(
    rig: DispatchRig, answer_resolved: bool
) -> None:
    node = _paused_slice(rig, answer_resolved=answer_resolved)
    block_and_resolve(rig.store, node, "resume")
    apply_pending_resolutions(rig.store, PROJECT, NodeContext())

    facts = _view(rig, node).facts[node.id]

    assert facts.state is DispatchState.RESUME


@pytest.mark.parametrize("answer_resolved", [False, True])
def test_the_checkout_stays_held_by_the_paused_runs_node(
    rig: DispatchRig, answer_resolved: bool
) -> None:
    node = _paused_slice(rig, answer_resolved=answer_resolved)
    entries = rig.store.journal_entries(PROJECT)

    holders = checkout_holders(entries, set())

    assert holders == {rig.world.root: frozenset({node.id})}


@pytest.mark.parametrize("answer_resolved", [False, True])
def test_the_resume_count_is_unchanged(rig: DispatchRig, answer_resolved: bool) -> None:
    node = _paused_slice(rig, answer_resolved=answer_resolved)
    [paused] = rig.entries(CommandKind.SQ_RUN, node)
    ended = RunEnded(RunOutcomeDocument.model_validate(paused_document("run-x")))

    assert _resume_count(rig.store, paused, ended) == 0


def test_an_sq_answer_resolution_awaits_no_routing(rig: DispatchRig) -> None:
    node = _paused_slice(rig, answer_resolved=True)
    [answer] = rig.entries(CommandKind.SQ_ANSWER, node)

    unrouted = rig.store.unrouted_outcomes(PROJECT)

    assert not answer.awaits_routing
    assert all(entry.kind is not CommandKind.SQ_ANSWER for entry in unrouted)


def test_supervision_entries_drops_only_sq_answer_and_keeps_order() -> None:
    def entry(index: int, kind: CommandKind) -> JournalEntry:
        return JournalEntry(id=f"e{index}", project_id="p", node_id="n", kind=kind)

    entries = [
        entry(1, CommandKind.SQ_RUN),
        entry(2, CommandKind.SQ_ANSWER),
        entry(3, CommandKind.CF_WRITE),
        entry(4, CommandKind.SQ_ANSWER),
        entry(5, CommandKind.SQ_RUN),
    ]

    kept = supervision_entries(entries)

    assert [e.id for e in kept] == ["e1", "e3", "e5"]


def test_supervision_entries_of_nothing_is_empty() -> None:
    assert supervision_entries([]) == []
