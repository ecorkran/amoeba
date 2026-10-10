"""`ingest review` with the process stopped, and into a project that is missing."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from cli_harness import (
    await_condition,
    run_cli,
    start_running,
    stop_running,
)
from ingest_e2e_harness import (
    applied,
    ingest_artifact,
    ingest_ok,
    inspect_rows,
    start_with_node,
)
from review_fixtures import ROUND_1_PART_1

from amoeba.cli.main import ExitCode
from amoeba.inbox import layout

MISSING_PROJECT = "nosuch"


@pytest.fixture
def supervisor_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "supervisor"
    directory.mkdir()
    return directory


@pytest.fixture
def runs_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "runs"
    directory.mkdir()
    return directory


def _inbox_listing(supervisor_dir: Path) -> list[object]:
    result = run_cli(["inspect", "inbox", "--json"], supervisor_dir)
    assert result.returncode == ExitCode.OK, result.stderr
    rows: list[object] = json.loads(result.stdout)
    return rows


def _assert_refused_cleanly(supervisor_dir: Path, node: str) -> None:
    result = ingest_artifact(
        supervisor_dir,
        node,
        ROUND_1_PART_1,
        "--upstream-version",
        "0.14.0",
        project=MISSING_PROJECT,
    )
    assert result.returncode == ExitCode.SUBMISSION_REFUSED, result.stderr
    assert MISSING_PROJECT in result.stderr
    assert layout.submission_files(layout.new_dir(supervisor_dir)) == []
    assert _inbox_listing(supervisor_dir) == []


def test_ingest_with_the_process_stopped_is_applied_on_the_next_start(
    supervisor_dir: Path, runs_dir: Path
) -> None:
    process, node = start_with_node(supervisor_dir, runs_dir)
    stop_running(supervisor_dir, process)

    submission_id = ingest_ok(supervisor_dir, node, ROUND_1_PART_1)
    assert len(layout.submission_files(layout.new_dir(supervisor_dir))) == 1

    process = start_running(supervisor_dir, runs_dir)
    try:
        await_condition(
            lambda: applied(supervisor_dir, submission_id), "the stopped-time ingest"
        )
        verdicts = inspect_rows(supervisor_dir, "verdicts")
        assert [(v["id"], v["node_id"]) for v in verdicts] == [(submission_id, node)]
    finally:
        stop_running(supervisor_dir, process)


def test_an_unknown_project_is_refused_with_the_process_running(
    supervisor_dir: Path, runs_dir: Path
) -> None:
    process, node = start_with_node(supervisor_dir, runs_dir)
    try:
        _assert_refused_cleanly(supervisor_dir, node)
    finally:
        stop_running(supervisor_dir, process)


def test_an_unknown_project_is_refused_with_the_process_stopped(
    supervisor_dir: Path, runs_dir: Path
) -> None:
    process, node = start_with_node(supervisor_dir, runs_dir)
    stop_running(supervisor_dir, process)
    _assert_refused_cleanly(supervisor_dir, node)
