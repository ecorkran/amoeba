"""Shared by the ``set_up`` tests: a routing fake ``cf`` and a one-call runner.

Directory lookups replay a recorded ``cf get --json`` fixture. A ``-p`` reference
replays that same recording with the project's id and name swapped in, for as many
projects as a test registers; an unregistered reference replays the recorded
``PROJECT_NOT_FOUND`` document.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from cf_fixtures import (
    DEFAULT_WORKTREE,
    OUTSIDE_ANY_PROJECT,
    fixture_document,
    replay,
)
from user_configs import user_config

from amoeba.config.user_config import UserConfig
from amoeba.operations.set_up import SetUpResult, set_up
from amoeba.store.store import Store

DIRECTORY = Path("/work/checkout")
#: The Context Forge id and name of the recorded default-worktree project.
RECORDED_ID: str = fixture_document(DEFAULT_WORKTREE)["id"]
RECORDED_NAME: str = fixture_document(DEFAULT_WORKTREE)["name"]


def project_document(project_id: str, name: str) -> dict[str, Any]:
    """The recorded project document with another project's id and name."""
    document = fixture_document(DEFAULT_WORKTREE)
    return {**document, "id": project_id, "name": name}


class FakeCf:
    """Routes ``cf get --json`` by working directory or ``-p`` reference."""

    def __init__(
        self,
        *,
        directory_fixture: str,
        projects: Sequence[tuple[str, str]] = (),
    ) -> None:
        self._directory_fixture = directory_fixture
        self._projects = [(RECORDED_ID, RECORDED_NAME), *projects]
        self.calls: list[list[str]] = []

    def __call__(
        self, argv: Sequence[str], **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        self.calls.append(list(argv))
        if "-p" not in argv:
            return replay(argv, self._directory_fixture)
        reference = argv[list(argv).index("-p") + 1]
        for project_id, name in self._projects:
            if reference in (project_id, name):
                text = json.dumps(project_document(project_id, name))
                return subprocess.CompletedProcess(list(argv), 0, text, "")
        return replay(argv, OUTSIDE_ANY_PROJECT)


def run_set_up(
    store: Store,
    document: object,
    *,
    config: UserConfig | None = None,
    directory_fixture: str = DEFAULT_WORKTREE,
    projects: Sequence[tuple[str, str]] = (),
) -> SetUpResult:
    return set_up(
        store,
        config if config is not None else user_config(),
        document,
        directory=DIRECTORY,
        run=FakeCf(directory_fixture=directory_fixture, projects=projects),
    )


def row_counts(store: Store) -> dict[str, int]:
    """Row count of each table ``set_up`` writes."""
    with store.read() as transaction:
        return {
            table: int(
                transaction.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
            )
            for table in ("programs", "members", "dependency_pairs")
        }
