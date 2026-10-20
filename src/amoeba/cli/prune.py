"""``amoeba prune sq-runs``: offer paused Squadron runs Amoeba is finished with.

Amoeba chooses, Squadron deletes, a human confirms. The default is a preview;
``--yes`` calls ``sq runs prune`` once for the chosen ids and never unlinks a
file itself. This is the one module that knows both the selection rule and the
store, and it opens stores read-only, so it works with the resident process
running or stopped.

The outcome is observed, not parsed: ``sq runs prune`` has no JSON output and its
exit status is not trusted (it exits 1 for a file someone else already removed,
which is still the goal state). After ``sq`` exits, the runs directory is read
again, and any candidate still present is reported.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from amoeba.process.observers.sq_runs import SquadronRun, parse_run_file
from amoeba.process.run_pruning import (
    PAUSED_STATUS,
    SQ_PRUNE_TIMEOUT_SECONDS,
    select_prunable,
)
from amoeba.process.settings import DEFAULT_SQ_RUNS_DIR
from amoeba.store import NodeStatus, Store, paths
from amoeba.store.discovery import discover_project_ids

if TYPE_CHECKING:  # pragma: no cover - typing only
    from amoeba.cli.main import ExitCode

#: The Squadron command that does the deleting.
SQ_EXECUTABLE = "sq"
SQ_PRUNE_ARGUMENTS = ("runs", "prune")
SQ_CONFIRM_FLAG = "--yes"

#: The one prune target this slice adds.
TARGET_SQ_RUNS = "sq-runs"


def add_prune_parser(subparsers: Any) -> None:
    """Add ``prune``. ``subparsers`` is typed ``Any`` for the reason in ``main.py``."""
    prune = subparsers.add_parser(
        "prune",
        help="Offer to prune what Amoeba is finished with.",
        description="Previews by default; deleting needs --yes.",
    )
    targets = prune.add_subparsers(dest="target", required=True)
    sq_runs = targets.add_parser(
        TARGET_SQ_RUNS,
        help="Paused Squadron runs Amoeba owns and no live node names.",
        description=(
            "Lists paused Squadron runs that Amoeba's journal owns, that no "
            "unfinished node names, and that have sat untouched for the "
            "retention period. With --yes, asks `sq runs prune` to delete them. "
            "Runs you launched yourself are never listed."
        ),
    )
    sq_runs.add_argument(
        "--yes", action="store_true", help="Delete the listed runs through sq."
    )


@dataclass(frozen=True)
class _Selection:
    """What one fresh read of the stores and the runs directory chose."""

    candidates: tuple[SquadronRun, ...]
    owners: dict[str, str]
    kept: int


def run_prune(args: argparse.Namespace) -> ExitCode:
    """Run ``amoeba prune``."""
    return prune_sq_runs(
        store_dir=paths.store_dir(),
        runs_dir=DEFAULT_SQ_RUNS_DIR,
        confirm=bool(args.yes),
        timeout_seconds=SQ_PRUNE_TIMEOUT_SECONDS,
        now=datetime.now(UTC),
    )


def prune_sq_runs(
    store_dir: Path,
    runs_dir: Path,
    *,
    confirm: bool,
    timeout_seconds: float,
    now: datetime,
) -> ExitCode:
    """Preview, or with ``confirm`` delete, the prunable paused runs.

    Raises:
        StoreError: A project's store could not be read. Nothing was selected
            and ``sq`` was not called: an unreadable store makes the held set
            incomplete, so the command refuses.
    """
    from amoeba.cli.main import ExitCode

    selection = _select(store_dir, runs_dir, now)
    _print_preview(selection)
    if not confirm or not selection.candidates:
        return ExitCode.OK

    note = _ask_sq_to_prune(selection.candidates, timeout_seconds)
    present = {run.run_id for run in _read_runs(runs_dir)}
    remaining = [run for run in selection.candidates if run.run_id in present]
    if not remaining:
        print(f"pruned {len(selection.candidates)} run(s)")
        return ExitCode.OK
    for run in remaining:
        print(f"still present: {run.run_id}", file=sys.stderr)
    print(note, file=sys.stderr)
    return ExitCode.PRUNE_INCOMPLETE


def _select(store_dir: Path, runs_dir: Path, now: datetime) -> _Selection:
    """Read every store and the runs directory afresh; nothing is carried over."""
    owned: dict[str, str] = {}
    held: set[str] = set()
    for project_id in discover_project_ids(store_dir):
        path = paths.project_store_path(store_dir, project_id)
        with Store.open_read_only(path) as store:
            owned.update(
                dict.fromkeys(store.recorded_result_run_ids(project_id), project_id)
            )
            held.update(
                node.sq.run_id
                for node in store.nodes_for_project(project_id)
                if node.status is not NodeStatus.DONE and node.sq.run_id
            )
    runs = _read_runs(runs_dir)
    candidates = select_prunable(runs, owned=owned, held=held, now=now)
    kept = sum(
        1 for run in runs if run.run_id in owned and run.status == PAUSED_STATUS
    ) - len(candidates)
    return _Selection(candidates, owned, kept)


def _read_runs(runs_dir: Path) -> list[SquadronRun]:
    """Every parseable run file. An unparseable one is logged by name, never chosen."""
    parsed = (parse_run_file(path) for path in sorted(runs_dir.glob("*.json")))
    return [run for run in parsed if run is not None]


def _print_preview(selection: _Selection) -> None:
    for run in selection.candidates:
        print(
            f"{run.run_id}\t{run.pipeline}\t{run.updated_at}\t"
            f"{selection.owners[run.run_id]}"
        )
    print(
        f"{len(selection.candidates)} run(s) to prune; "
        f"{selection.kept} owned paused run(s) kept"
    )


def _ask_sq_to_prune(candidates: Sequence[SquadronRun], timeout_seconds: float) -> str:
    """Run ``sq runs prune`` once. Returns a note for the report if it went wrong.

    The note is only read when a candidate is still present afterwards, because
    ``sq``'s exit status does not decide the outcome (see the module docstring).
    """
    command = [
        SQ_EXECUTABLE,
        *SQ_PRUNE_ARGUMENTS,
        *(run.run_id for run in candidates),
        SQ_CONFIRM_FLAG,
    ]
    try:
        completed = subprocess.run(
            command,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except FileNotFoundError:
        # Specific: `sq` is not on PATH. Amoeba never deletes a file itself, so
        # the candidates simply remain and the command reports incomplete.
        return f"`{SQ_EXECUTABLE}` was not found on PATH"
    except subprocess.TimeoutExpired:
        # Specific: subprocess.run has already killed and reaped `sq`. Running
        # the command again selects afresh and converges.
        return f"`{SQ_EXECUTABLE}` did not finish within {timeout_seconds} seconds"
    return (
        f"`{SQ_EXECUTABLE}` exited {completed.returncode}: {completed.stderr.strip()}"
    )
