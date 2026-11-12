"""Layouts and legacy homes for the state-move tests (slice 228, D2).

Both homes are explicit throwaway paths under ``tmp_path``; none is ``Path.home``.
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

from store.relocate_support import RUN_IDS, seed_store

from amoeba.config.home import StateLayout
from amoeba.operations.state_move_types import MoveStep

SELECT_ANSWERS = "SELECT seq, run_id, resume_log FROM answers ORDER BY seq"
SELECT_COUNTS = (
    "SELECT (SELECT COUNT(*) FROM questions), (SELECT COUNT(*) FROM answers)"
    ", (SELECT COUNT(*) FROM members)"
)
ANSWERING_SCRATCH = "answering-run-1"


class Crash(Exception):
    """Raised by a test's ``after_step`` to simulate the process dying there."""


def crash_after(step: MoveStep):  # noqa: ANN201
    """An ``after_step`` that raises ``Crash`` once ``step`` completes."""

    def hook(reached: MoveStep) -> None:
        if reached is step:
            raise Crash(step.value)

    return hook


def make_layout(tmp_path: Path) -> StateLayout:
    state = tmp_path / "state"
    return StateLayout(
        state_home=state,
        store_path=state / "amoeba.sqlite3",
        answering_dir=state / "answering",
        logs_dir=state / "logs",
        calls_log_dir=state / "logs" / "calls",
        legacy_home=tmp_path / "legacy",
    )


def seed_legacy_home(layout: StateLayout) -> Path:
    """A legacy home with a store, scratch, logs and the config; returns the store."""
    legacy = layout.legacy_home
    assert legacy is not None
    store = seed_store(legacy)
    scratch = legacy / "answering" / ANSWERING_SCRATCH
    scratch.mkdir(parents=True)
    (scratch / "prompt.txt").write_text("scratch", encoding="utf-8")
    (legacy / "logs" / "answering").mkdir(parents=True)
    (legacy / "logs" / "answering" / f"{ANSWERING_SCRATCH}.stdout.log").write_text(
        "out", encoding="utf-8"
    )
    resume = legacy / "logs" / "resume" / RUN_IDS[0]
    resume.mkdir(parents=True)
    (resume / "1.log").write_text("resume", encoding="utf-8")
    (legacy / "config.yaml").write_text("answer_limit: 3\n", encoding="utf-8")
    return store


def rows(store: Path, statement: str) -> list[tuple[object, ...]]:
    with closing(sqlite3.connect(store)) as connection:
        return [tuple(row) for row in connection.execute(statement)]


def legacy_leftovers(layout: StateLayout) -> list[str]:
    """Everything left in the legacy home, by relative path."""
    legacy = layout.legacy_home
    assert legacy is not None
    return sorted(str(path.relative_to(legacy)) for path in legacy.rglob("*"))
