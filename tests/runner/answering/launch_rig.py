"""A store, a repository and fakes, ready to launch an answering run (slice 144)."""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from answerer_settings import answerer_settings
from cf_harness import observed
from question_harness import PROJECT, catch_for
from sq_stub_scripts import answering_run

from amoeba.process import RunOutcome, RunOutcomeDocument
from amoeba.runner.answering.launch import LaunchContext, LaunchStatus, launch_answering
from amoeba.runner.answering.stage import AnsweringStage, StageResult
from amoeba.runner.budget import TickBudget
from amoeba.runner.faults import NodeContext, TickFaults
from amoeba.runner.launch import LAUNCH_LOGS_DIRNAME, LaunchTracker, PopenFactory
from amoeba.runner.observe import RunObserver
from amoeba.runner.project_config import AnswererSettings
from amoeba.store import (
    CFReference,
    JournalEntry,
    Node,
    NodeKind,
    QuestionRecord,
    Store,
)
from amoeba.upstream.context_forge import (
    FIELD_PROJECT_PATH,
    STATE_PROJECT_KEY,
    STATE_WORKTREES_KEY,
)
from runner.answering.sources_repo import CountingBudget, build_sources_repo
from runner.observe_support import Clock, Host, ScriptedPoll

CF_ID = "project_1_abc"
SLICE_INDEX = 132
INITIATIVE_INDEX = 120
NOW = datetime(2026, 11, 3, 12, 0, tzinfo=UTC)
CALL_TIMEOUT = 8.0


class QuietChild:
    """A child that is still running."""

    def poll(self) -> int | None:
        return None


class RecordingPopen:
    """Records each start (argv and working directory); optionally raises."""

    def __init__(self, error: OSError | None = None) -> None:
        self.error = error
        self.calls: list[tuple[list[str], str]] = []

    def __call__(self, argv: list[str], **kwargs: Any) -> QuietChild:
        self.calls.append((argv, str(kwargs["cwd"])))
        if self.error is not None:
            raise self.error
        return QuietChild()


def cf_run(
    target: str = "main",
) -> Callable[..., subprocess.CompletedProcess[str]]:
    """``cf`` answers with ``target``; ``git`` runs for real."""

    def run(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if argv[0] == "cf":
            body = f'{{"value": "{target}"}}'
            return subprocess.CompletedProcess(argv, 0, body, "")
        return cast("subprocess.CompletedProcess[str]", subprocess.run(argv, **kwargs))

    return run


def budget() -> TickBudget:
    return TickBudget(1_000.0, Host(), Clock().monotonic)


def default_settings() -> AnswererSettings:
    """Settings that read the fixture repository's ``CLAUDE.md`` whole."""
    return answerer_settings(rules_paths=("CLAUDE.md",), passages_max_chars=1_000_000)


@dataclass(frozen=True)
class LaunchRig:
    """The context and one pending question of a slice in a real repository."""

    store: Store
    context: LaunchContext
    record: QuestionRecord
    node: Node
    popen: RecordingPopen
    supervisor_dir: Path
    initiative: Node

    def other_slice(self, title: str, number: int) -> Node:
        """A second slice of the same initiative, with no question yet."""
        return _slice(self.store, self.initiative, title, SLICE_INDEX + number)

    def ask_another(
        self, number: int = 1, question: str = "which branch?"
    ) -> QuestionRecord:
        """Another pending question on a fresh slice of the same initiative."""
        title = f"Other Slice {number}"
        other = _slice(self.store, self.initiative, title, SLICE_INDEX + number)
        return _ask(self.store, other, question)


def _initiative(store: Store) -> Node:
    return store.create_node(
        project_id=PROJECT,
        kind=NodeKind.INITIATIVE,
        title="Initiative",
        cf=CFReference(project=CF_ID, index=INITIATIVE_INDEX),
    )


def _slice(store: Store, parent: Node, title: str, index: int) -> Node:
    return store.create_node(
        project_id=PROJECT,
        kind=NodeKind.SLICE,
        title=title,
        parent_id=parent.id,
        cf=CFReference(project=CF_ID, index=index),
    )


def _ask(store: Store, node: Node, question: str = "which branch?") -> QuestionRecord:
    return store.record_question(
        catch_for(store, node.id, question=question),
        block_context="ctx",
        block_payload=None,
    )


def build_launch_rig(
    tmp_path: Path,
    store: Store,
    *,
    popen: RecordingPopen | None = None,
    settings: AnswererSettings | None = None,
    popen_factory: PopenFactory | None = None,
    question: str = "which branch?",
) -> LaunchRig:
    """A pending question on slice 132 of the fixture repository.

    ``popen_factory`` replaces the recording fake (the live tier starts real
    ``sq``); ``popen`` is then unused.
    """
    repo = build_sources_repo(tmp_path / "repo")
    state = {
        STATE_PROJECT_KEY: {FIELD_PROJECT_PATH: str(repo.path)},
        STATE_WORKTREES_KEY: {},
    }
    store.record_cf_snapshot(observed(PROJECT, CF_ID, state=state, changed=[]))
    supervisor_dir = tmp_path / "supervisor"
    (supervisor_dir / LAUNCH_LOGS_DIRNAME).mkdir(parents=True)
    initiative = _initiative(store)
    node = _slice(store, initiative, "Pipeline Supervisor", SLICE_INDEX)
    recording = popen or RecordingPopen()
    context = LaunchContext(
        store=store,
        project_id=PROJECT,
        settings=settings or default_settings(),
        supervisor_dir=supervisor_dir,
        popen=popen_factory or recording,
        tracker=LaunchTracker(),
        now=lambda: NOW,
        cf_run=cf_run(),
        call_timeout_seconds=CALL_TIMEOUT,
    )
    return LaunchRig(
        store,
        context,
        _ask(store, node, question),
        node,
        recording,
        supervisor_dir,
        initiative,
    )


@dataclass(frozen=True)
class StageRig:
    """A launch rig plus the stage over it, with a scripted poll."""

    launch: LaunchRig
    stage: AnsweringStage
    poll: ScriptedPoll
    node_context: NodeContext

    @property
    def store(self) -> Store:
        return self.launch.store

    def run(self, allowed: int | None = None) -> StageResult:
        """One stage pass; ``allowed`` limits the calls the budget grants."""
        spend = budget() if allowed is None else CountingBudget(allowed)
        return self.stage.run(spend, TickFaults())

    def start(self, record: QuestionRecord) -> JournalEntry:
        """Launch the record's run and mark it confirmed, as its first line would."""
        status = launch_answering(self.launch.context, record, budget())
        assert status is LaunchStatus.STARTED, status
        reloaded = self.store.question(record.id)
        assert reloaded is not None and reloaded.answering_entry_id is not None
        entry = self.store.journal_entry(reloaded.answering_entry_id)
        assert entry is not None
        self.launch.context.tracker.confirm(entry.id)
        return entry


def build_stage_rig(
    tmp_path: Path,
    store: Store,
    *,
    settings: AnswererSettings | None = None,
    popen: RecordingPopen | None = None,
) -> StageRig:
    """The stage over a launch rig; its polls answer from ``StageRig.poll``."""
    rig = build_launch_rig(tmp_path, store, settings=settings, popen=popen)
    clock = Clock()
    poll = ScriptedPoll()
    observer = RunObserver(
        supervisor_dir=rig.supervisor_dir,
        tracker=rig.context.tracker,
        poll=poll,
        now=clock.wall,
        monotonic=clock.monotonic,
        launch_grace_seconds=60.0,
        run_poll_interval_seconds=15.0,
    )
    node_context = NodeContext()
    stage = AnsweringStage(
        store=store,
        project_id=PROJECT,
        launch=rig.context,
        observer=observer,
        node_context=node_context,
    )
    return StageRig(rig, stage, poll, node_context)


def run_document(entry: JournalEntry, outcome: RunOutcome) -> RunOutcomeDocument:
    """The poll answer for the entry's run."""
    return RunOutcomeDocument(
        run_id=str(entry.parameters["run_id"]), outcome=outcome, status=outcome.value
    )


def write_replies(
    entry: JournalEntry,
    answer: Mapping[str, object] | str | None,
    check: Mapping[str, object] | str | None,
) -> None:
    """Write ``answer.json`` and ``check.json`` into the entry's scratch directory."""
    scratch = Path(str(entry.parameters["scratch"]))
    for name, content in answering_run(answer, check).files.items():
        (scratch / name).write_text(content, encoding="utf-8")
