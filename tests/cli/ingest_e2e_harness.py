"""Setup and read-back shared by the ``ingest review`` end-to-end tests.

Everything runs as real subprocesses against a throwaway supervisor directory
under pytest's ``tmp_path``; none of it can reach the real one.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from cli_harness import (
    BackgroundCli,
    CommandResult,
    await_condition,
    cli_environment,
    run_cli,
    start_running,
    stop_running,
    submit_cli,
)

from amoeba.cli.main import ExitCode
from amoeba.store import Store, SubmissionOutcome

PROJECT = "demo"
OPERATOR = "pm"
#: Every 102 fixture predates Squadron's version stamp.
PRE_STAMP_LABEL = "0.14.0"
DEMO_SCRIPT = Path(__file__).parents[2] / "scripts" / "demo_evidence.py"


def store_file(supervisor_dir: Path) -> Path:
    return supervisor_dir / f"{PROJECT}.sqlite3"


def seed_node(supervisor_dir: Path) -> str:
    """Seed the demo node (the process must be stopped) and return its id."""
    result = subprocess.run(
        [sys.executable, str(DEMO_SCRIPT)],
        capture_output=True,
        text=True,
        env=cli_environment(supervisor_dir),
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def start_with_node(supervisor_dir: Path, runs_dir: Path) -> tuple[BackgroundCli, str]:
    """From an empty directory: create the project, seed a node, leave it running."""
    process = start_running(supervisor_dir, runs_dir)
    created = submit_cli(supervisor_dir, PROJECT, "create-project", "--by", OPERATOR)
    await_condition(lambda: applied(supervisor_dir, created), "project creation")
    stop_running(supervisor_dir, process)
    node = seed_node(supervisor_dir)
    return start_running(supervisor_dir, runs_dir), node


def applied(supervisor_dir: Path, *submission_ids: str) -> bool:
    """Whether every submission has been applied (read-only; false if no store)."""
    if not store_file(supervisor_dir).is_file():
        return False
    with Store.open_read_only(store_file(supervisor_dir)) as store:
        records = [store.submission(sid) for sid in submission_ids]
    return all(
        r is not None and r.outcome is SubmissionOutcome.APPLIED for r in records
    )


def ingest_artifact(
    supervisor_dir: Path, node: str, path: Path, *extra: str, project: str = PROJECT
) -> CommandResult:
    return run_cli(
        [
            "ingest",
            "review",
            "--project",
            project,
            "--node",
            node,
            "--by",
            OPERATOR,
            "--artifact",
            str(path),
            *extra,
        ],
        supervisor_dir,
    )


def ingest_ok(supervisor_dir: Path, node: str, path: Path, *extra: str) -> str:
    """Ingest a pre-stamp review file; returns the printed submission id."""
    result = ingest_artifact(
        supervisor_dir, node, path, "--upstream-version", PRE_STAMP_LABEL, *extra
    )
    assert result.returncode == ExitCode.OK, result.stderr
    return result.stdout.strip()


def inspect_rows(supervisor_dir: Path, *arguments: str) -> list[dict[str, object]]:
    result = run_cli(
        ["inspect", *arguments, "--project", PROJECT, "--json"], supervisor_dir
    )
    assert result.returncode == ExitCode.OK, result.stderr
    rows: list[dict[str, object]] = json.loads(result.stdout)
    return rows
