"""Pruning (slice 228, D9): settled scratch, logs and calls-log days older than a limit.

``prune`` is called at the end of ``handle_pause`` and ``status``, and does its walk
at most once per ``PRUNE_INTERVAL`` (the mtime of one marker file in the state home),
so a burst of hook calls does not each walk every log. Everything tied to an
open question is kept whatever its age: it is evidence for the PM and for the
dead-claim path. The store's rows are never pruned. An ``OSError`` on one entry goes
into ``PruneReport.problems`` and the other entries are still pruned.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Final

from amoeba.config.home import CALLS_LOG_DIR_NAME, StateLayout
from amoeba.operations.answering_run import (
    ANSWERING_LOG_DIRECTORY,
    STDERR_LOG_SUFFIX,
    STDOUT_LOG_SUFFIX,
)
from amoeba.operations.calls_log import DAY_FILE_SUFFIX, DAY_FORMAT
from amoeba.operations.prune_models import PruneReport
from amoeba.operations.resume import RESUME_LOG_DIRECTORY
from amoeba.store.question_closing import (
    open_answering_run_ids,
    run_ids_with_open_question,
)
from amoeba.store.store import Store

#: Directories under ``logs/`` that are never removed, even when empty.
PROTECTED_LOG_DIRECTORIES: Final = (
    ANSWERING_LOG_DIRECTORY,
    RESUME_LOG_DIRECTORY,
    CALLS_LOG_DIR_NAME,
)
#: The marker whose mtime is the time of the last walk; one fixed-name file, so
#: nothing accumulates, and deleting it only makes the next call walk.
PRUNE_MARKER_NAME: Final = ".last-prune"
PRUNE_INTERVAL: Final = timedelta(hours=1)
ANSWERING_LOG_SUFFIXES: Final = (STDOUT_LOG_SUFFIX, STDERR_LOG_SUFFIX)


@dataclass(frozen=True)
class _Evidence:
    """What open questions hold: answering run ids and run ids."""

    answering_run_ids: frozenset[str]
    run_ids: frozenset[str]


class _Pass:
    """One prune pass: the cutoff, the evidence, and what has been removed."""

    def __init__(self, layout: StateLayout, now: datetime, after_days: int) -> None:
        self._layout = layout
        cutoff = now.astimezone(UTC) - timedelta(days=after_days)
        self._cutoff_seconds = cutoff.timestamp()
        self._cutoff_date: date = cutoff.date()
        self.removed = 0
        self.problems: list[str] = []

    def run(self, evidence: _Evidence) -> None:
        self._prune_scratch(evidence.answering_run_ids)
        self._prune_logs(evidence)

    # --- answering scratch ---------------------------------------------------

    def _prune_scratch(self, open_ids: frozenset[str]) -> None:
        for entry in self._entries(self._layout.answering_dir):
            if entry.name in open_ids or not self._older(entry):
                continue
            self._remove(entry)

    # --- logs ----------------------------------------------------------------

    def _prune_logs(self, evidence: _Evidence) -> None:
        logs = self._layout.logs_dir
        for root, _directories, names in os.walk(logs):
            for name in names:
                file = Path(root) / name
                relative = file.relative_to(logs).parts
                if self._removable_log(file, relative, evidence):
                    self._remove(file)
                    self._remove_emptied_directories(file.parent)

    def _removable_log(
        self, file: Path, relative: tuple[str, ...], evidence: _Evidence
    ) -> bool:
        match relative:
            case (directory, name) if directory == ANSWERING_LOG_DIRECTORY and (
                name.endswith(ANSWERING_LOG_SUFFIXES)
            ):
                run_id = name.removesuffix(STDOUT_LOG_SUFFIX).removesuffix(
                    STDERR_LOG_SUFFIX
                )
                return run_id not in evidence.answering_run_ids and self._older(file)
            case (directory, run_id, _name) if directory == RESUME_LOG_DIRECTORY:
                return run_id not in evidence.run_ids and self._older(file)
            case (directory, name) if directory == CALLS_LOG_DIR_NAME:
                logged = _day_of(name)
                if logged is not None:
                    return logged < self._cutoff_date
            case _:
                pass
        return self._older(file)

    def _remove_emptied_directories(self, directory: Path) -> None:
        """Remove ``directory`` and its parents while they are empty, up to the
        protected ones."""
        logs = self._layout.logs_dir
        while directory != logs and not _is_protected(directory, logs):
            try:
                directory.rmdir()
            except OSError:
                # Not empty (a file is still there or has arrived), or already gone:
                # either way it is not ours to remove.
                return
            directory = directory.parent

    # --- shared --------------------------------------------------------------

    def _entries(self, directory: Path) -> list[Path]:
        try:
            return sorted(directory.iterdir())
        except FileNotFoundError:
            # Nothing was ever written there, which is not a problem.
            return []
        except OSError as error:
            self.problems.append(f"prune: cannot list {directory}: {error}")
            return []

    def _older(self, path: Path) -> bool:
        try:
            return path.lstat().st_mtime < self._cutoff_seconds
        except FileNotFoundError:
            # Removed by someone else since it was listed: nothing to prune.
            return False
        except OSError as error:
            self.problems.append(f"prune: cannot read {path}: {error}")
            return False

    def _remove(self, path: Path) -> None:
        try:
            if path.is_dir() and not path.is_symlink():
                shutil.rmtree(path)
            else:
                path.unlink()
        except FileNotFoundError:
            # Already gone: the goal is met.
            return
        except OSError as error:
            # One locked or unreadable entry must not fail the call that triggered
            # pruning: it is named in the report and the others are still pruned.
            self.problems.append(f"prune: cannot remove {path}: {error}")
            return
        self.removed += 1


def _is_protected(directory: Path, logs: Path) -> bool:
    return directory.parent == logs and directory.name in PROTECTED_LOG_DIRECTORIES


def _day_of(file_name: str) -> date | None:
    """The date in a calls-log day file name, or ``None`` if it is not one."""
    if not file_name.endswith(DAY_FILE_SUFFIX):
        return None
    try:
        return datetime.strptime(
            file_name.removesuffix(DAY_FILE_SUFFIX), DAY_FORMAT
        ).date()
    except ValueError:
        # Not a day file: the caller prunes it by age like any other file.
        return None


def _pruned_recently(marker: Path, now: datetime) -> bool:
    try:
        walked_at = marker.stat().st_mtime
    except FileNotFoundError:
        return False  # never walked
    return 0 <= now.timestamp() - walked_at < PRUNE_INTERVAL.total_seconds()


def _mark_walked(marker: Path, now: datetime) -> str | None:
    """Record the walk at ``now``; the problem text if it could not be recorded."""
    try:
        marker.touch()
        os.utime(marker, (now.timestamp(), now.timestamp()))
    except FileNotFoundError:
        return None  # no state home, so nothing was there to walk
    except OSError as error:
        return f"prune: cannot record the walk in {marker}: {error}"
    return None


def prune(
    store: Store, layout: StateLayout, now: datetime, after_days: int
) -> PruneReport:
    """Remove settled and orphaned scratch and logs older than ``after_days``;
    nothing if the last walk was under ``PRUNE_INTERVAL`` ago.

    Raises:
        StoreError: The open questions could not be read.
    """
    marker = layout.state_home / PRUNE_MARKER_NAME
    if _pruned_recently(marker, now):
        return PruneReport(0, ())
    with store.read() as transaction:
        evidence = _Evidence(
            open_answering_run_ids(transaction), run_ids_with_open_question(transaction)
        )
    state = _Pass(layout, now, after_days)
    state.run(evidence)
    marking_problem = _mark_walked(marker, now)
    problems = (*state.problems, *([marking_problem] if marking_problem else []))
    return PruneReport(state.removed, problems)
