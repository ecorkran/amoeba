"""A store, a repository and fakes, ready to launch an answering run (slice 144)."""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from answerer_settings import answerer_settings
from cf_harness import observed
from question_harness import PROJECT, catch_for

from amoeba.runner.answering.launch import LaunchContext
from amoeba.runner.budget import TickBudget
from amoeba.runner.launch import LAUNCH_LOGS_DIRNAME, LaunchTracker
from amoeba.runner.project_config import AnswererSettings
from amoeba.store import (
    CFReference,
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
from runner.answering.sources_repo import build_sources_repo
from runner.observe_support import Clock, Host

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

    def ask_another(self) -> QuestionRecord:
        """Another pending question on a fresh slice of the same initiative."""
        other = _slice(self.store, self.initiative, "Other Slice", SLICE_INDEX + 1)
        return _ask(self.store, other)


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
) -> LaunchRig:
    """A pending question on slice 132 of the fixture repository."""
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
        popen=recording,
        tracker=LaunchTracker(),
        now=lambda: NOW,
        cf_run=cf_run(),
        call_timeout_seconds=CALL_TIMEOUT,
    )
    return LaunchRig(
        store, context, _ask(store, node), node, recording, supervisor_dir, initiative
    )
