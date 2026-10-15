"""`ingest review` with the process stopped, into a missing project, and both ways."""

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
    OPERATOR,
    PROJECT,
    applied,
    ingest_artifact,
    ingest_ok,
    inspect_rows,
    start_with_node,
)
from review_fixtures import PAIR_ARTIFACT, PAIR_STDOUT, ROUND_1_PART_1

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


def _ingest_stdout(supervisor_dir: Path, node: str, path: Path) -> str:
    result = run_cli(
        [
            "ingest",
            "review",
            "--project",
            PROJECT,
            "--node",
            node,
            "--by",
            OPERATOR,
            "--stdout-json",
            str(path),
        ],
        supervisor_dir,
    )
    assert result.returncode == ExitCode.OK, result.stderr
    return result.stdout.strip()


def test_one_review_ingested_as_stdout_and_as_its_file_is_seen_twice(
    supervisor_dir: Path, runs_dir: Path
) -> None:
    process, node = start_with_node(supervisor_dir, runs_dir)
    try:
        stdout_id = _ingest_stdout(supervisor_dir, node, PAIR_STDOUT)
        artifact = ingest_artifact(supervisor_dir, node, PAIR_ARTIFACT)
        assert artifact.returncode == ExitCode.OK, artifact.stderr
        artifact_id = artifact.stdout.strip()
        assert stdout_id != artifact_id
        await_condition(
            lambda: applied(supervisor_dir, stdout_id, artifact_id), "the pair"
        )
        verdicts = {v["id"]: v for v in inspect_rows(supervisor_dir, "verdicts")}
        assert verdicts[stdout_id]["source"] == "stdout_json"
        assert verdicts[stdout_id]["reviewed_sha"] is None
        assert verdicts[artifact_id]["source"] == "artifact_frontmatter"
        assert verdicts[artifact_id]["reviewed_sha"] == (
            "0c8a499b4df3639cbd9c2af1f6201c5cf920bdc2"
        )
        findings = inspect_rows(supervisor_dir, "findings", "--node", node)
        assert len(findings) == 6
        assert all(row["times_seen"] == 2 for row in findings)
    finally:
        stop_running(supervisor_dir, process)
