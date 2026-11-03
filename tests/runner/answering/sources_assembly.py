"""Helpers that run `assemble_sources` over a node tree and a repository."""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from answerer_settings import answerer_settings
from cf_harness import observed
from question_harness import PROJECT, seed_question

from amoeba.runner.answering.sources import assemble_sources
from amoeba.runner.budget import TickBudget
from amoeba.runner.project_config import AnswererSettings
from amoeba.store import CFReference, CFSnapshot, Node, NodeKind, Store
from amoeba.upstream.context_forge import (
    FIELD_PROJECT_PATH,
    STATE_PROJECT_KEY,
    STATE_WORKTREES_KEY,
)
from runner.observe_support import Clock, Host

CF_ID = "project_1_abc"
TIMEOUT = 8.0


def settings(*rules: str, max_chars: int = 1_000_000) -> AnswererSettings:
    return answerer_settings(rules_paths=rules, passages_max_chars=max_chars)


def node(
    store: Store, kind: NodeKind, title: str, index: int | None, parent: str | None
) -> Node:
    return store.create_node(
        project_id=PROJECT,
        kind=kind,
        title=title,
        parent_id=parent,
        cf=CFReference(index=index),
    )


def slice_node(
    store: Store, index: int = 132, title: str = "Demo Slice", initiative: int = 120
) -> Node:
    parent = node(store, NodeKind.INITIATIVE, "Initiative", initiative, None)
    return node(store, NodeKind.SLICE, title, index, parent.id)


def snapshot(store: Store, project_path: Path) -> CFSnapshot:
    state = {
        STATE_PROJECT_KEY: {FIELD_PROJECT_PATH: str(project_path)},
        STATE_WORKTREES_KEY: {},
    }
    return store.record_cf_snapshot(observed(PROJECT, CF_ID, state=state, changed=[]))


def run(
    target: str = "main", cf_exit: int = 0
) -> Callable[..., subprocess.CompletedProcess[str]]:
    """``cf`` answers with ``target`` (or fails); ``git`` runs for real."""

    def runner(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if argv[0] == "cf":
            body = f'{{"value": "{target}"}}' if cf_exit == 0 else "cf broke"
            return subprocess.CompletedProcess(argv, cf_exit, body, "")
        return cast("subprocess.CompletedProcess[str]", subprocess.run(argv, **kwargs))

    return runner


def budget() -> TickBudget:
    return TickBudget(1_000.0, Host(), Clock().monotonic)


def assemble(store: Store, slice_: Node, snap: CFSnapshot | None, **kw: Any) -> Any:
    record = seed_question(store, slice_.id)
    return assemble_sources(
        store,
        PROJECT,
        record,
        snap,
        CF_ID,
        kw.get("settings", settings("CLAUDE.md")),
        kw.get("budget", budget()),
        kw.get("run", run()),
        TIMEOUT,
    )
