"""Recovery of an ``sq_answer`` entry by its run id (slice 144, D2).

Same observer as an ``sq_run`` with a run id, driven through the stub ``sq``.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from sq_stub import write_outcome_document, write_sq_stub

from amoeba.process.recovery import RecoverySummary, reconcile
from amoeba.process.settings import ProcessSettings
from amoeba.process.sq_outcome import RunOutcome
from amoeba.process.supervisor import build_observer_registry
from amoeba.store import CommandKind, JournalOutcome, Node, NodeKind, Store

PROJECT = "demo"
RUN_ID = "run-answer-recovery-1"
IN_FLIGHT_OUTCOMES = [
    RunOutcome.PAUSED,
    RunOutcome.COMPLETED,
    RunOutcome.FAILED,
    RunOutcome.ORPHANED,
]


@pytest.fixture
def node(store: Store) -> Node:
    return store.create_node(project_id=PROJECT, kind=NodeKind.SLICE, title="answered")


def _stub_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, ProcessSettings]:
    """The stub ``sq`` first on ``PATH`` under a scratch ``HOME``; no launch grace."""
    home = tmp_path / "home"
    home.mkdir()
    bin_dir = write_sq_stub(tmp_path / "bin")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    return home, ProcessSettings(
        sq_runs_dir=tmp_path / "runs", launch_grace_seconds=0.0
    )


def _issue_answer(store: Store, node: Node) -> str:
    return store.journal_issue(
        node.id,
        kind=CommandKind.SQ_ANSWER,
        parameters={
            "run_id": RUN_ID,
            "pipeline": "answering.yaml",
            "params": {},
            "scratch": "/tmp/answering/scratch",
        },
    ).id


def _document(outcome: RunOutcome) -> dict[str, object]:
    return {"run_id": RUN_ID, "outcome": outcome.value, "status": outcome.value}


@pytest.mark.parametrize("outcome", IN_FLIGHT_OUTCOMES)
def test_an_answer_run_in_any_state_stays_unresolved(
    store: Store,
    node: Node,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    outcome: RunOutcome,
) -> None:
    home, settings = _stub_home(tmp_path, monkeypatch)
    write_outcome_document(home, _document(outcome))
    entry_id = _issue_answer(store, node)

    summary = reconcile(store, PROJECT, build_observer_registry(settings))

    entry = store.journal_entry(entry_id)
    assert entry is not None and not entry.is_resolved
    assert summary == RecoverySummary(in_flight=1)


def test_an_answer_run_with_no_state_past_grace_is_not_applied(
    store: Store, node: Node, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, settings = _stub_home(tmp_path, monkeypatch)
    entry_id = _issue_answer(store, node)

    summary = reconcile(store, PROJECT, build_observer_registry(settings))

    entry = store.journal_entry(entry_id)
    assert entry is not None and entry.outcome is JournalOutcome.NOT_APPLIED
    assert summary == RecoverySummary(not_applied=1)


def test_an_unreadable_answer_run_escalates_with_one_block(
    store: Store, node: Node, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home, settings = _stub_home(tmp_path, monkeypatch)
    write_outcome_document(home, _document(RunOutcome.UNREADABLE))
    entry_id = _issue_answer(store, node)
    registry = build_observer_registry(settings)

    first = reconcile(store, PROJECT, registry)
    second = reconcile(store, PROJECT, registry)

    entry = store.journal_entry(entry_id)
    assert entry is not None and entry.outcome is JournalOutcome.UNKNOWN
    assert first == RecoverySummary(unknown=1)
    assert second == RecoverySummary()
    open_blocks = [s for s in store.all_blocked_states(node.id) if not s.is_resolved]
    assert len(open_blocks) == 1
