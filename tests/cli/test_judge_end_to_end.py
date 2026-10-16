"""Slice 107 end to end: judge samples and a check through the real CLI.

From an empty supervisor directory: create the project, seed a node, ingest the
real judge review under ``j1``, submit two more ``j1`` samples and a check that
examined nothing, ``kill -9`` the process, start it again. Read-only inspection
then shows three samples, the calibration row, a ``vacuous`` check, nothing
applied twice, and one feed change per record.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from cli_harness import (
    await_condition,
    await_stopped,
    run_cli,
    start_running,
    stop_running,
    submit_cli,
)
from ingest_e2e_harness import (
    OPERATOR,
    PROJECT,
    applied,
    ingest_artifact,
    inspect_rows,
    start_with_node,
)
from review_fixtures import JUDGE_REVIEW_107

from amoeba.cli.main import ExitCode
from amoeba.inbox import pending

INVOCATION = "j1"
EXTRA_SAMPLES = ("sample-2", "sample-3")


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


def _submit_sample(supervisor_dir: Path, node: str, sample_id: str) -> str:
    return submit_cli(
        supervisor_dir,
        PROJECT,
        "verdict",
        "--by",
        OPERATOR,
        "--id",
        sample_id,
        "--node-id",
        node,
        "--verdict",
        "PASS",
        "--derivation",
        "not_reported",
        "--fallback-used",
        "null",
        "--findings-parsed",
        "true",
        "--provider-failure",
        "false",
        "--review-type",
        "judge.slice-vs-arch",
        "--model",
        "claude-sonnet-5-5",
        "--findings",
        "[]",
        "--upstream",
        "squadron",
        "--upstream-version",
        "0.22.0",
        "--source",
        "artifact_frontmatter",
        "--score",
        "80",
        "--judge-invocation-id",
        INVOCATION,
    )


def _submit_vacuous_check(supervisor_dir: Path, node: str) -> str:
    return submit_cli(
        supervisor_dir,
        PROJECT,
        "check",
        "--by",
        OPERATOR,
        "--id",
        "check-1",
        "--node-id",
        node,
        "--name",
        "export-docs",
        "--outcome",
        "passed",
        "--examined-count",
        "0",
        "--upstream",
        "squadron",
        "--upstream-version",
        "0.22.0",
        "--source",
        "command_output",
    )


def _feed(supervisor_dir: Path) -> list[dict[str, object]]:
    result = run_cli(["feed", "--project", PROJECT], supervisor_dir)
    assert result.returncode == ExitCode.OK, result.stderr
    return [json.loads(line) for line in result.stdout.splitlines()]


def test_judge_samples_and_a_check_end_to_end(
    supervisor_dir: Path, runs_dir: Path
) -> None:
    process, node = start_with_node(supervisor_dir, runs_dir)
    ingested = ingest_artifact(
        supervisor_dir,
        node,
        JUDGE_REVIEW_107,
        "--judge-invocation-id",
        INVOCATION,
    )
    assert ingested.returncode == ExitCode.OK, ingested.stderr
    sample_ids = [ingested.stdout.strip()]
    sample_ids += [_submit_sample(supervisor_dir, node, s) for s in EXTRA_SAMPLES]
    check_id = _submit_vacuous_check(supervisor_dir, node)
    await_condition(
        lambda: applied(supervisor_dir, *sample_ids, check_id), "samples and check"
    )
    await_condition(lambda: pending(supervisor_dir) == [], "the inbox to drain")

    process.kill_and_wait()
    process.cleanup()
    await_stopped(supervisor_dir)
    process = start_running(supervisor_dir, runs_dir)
    stop_running(supervisor_dir, process)

    verdicts = inspect_rows(supervisor_dir, "verdicts", "--node", node)
    assert sorted(str(v["id"]) for v in verdicts) == sorted(sample_ids)
    assert {v["judge_invocation_id"] for v in verdicts} == {INVOCATION}

    (calibration,) = inspect_rows(supervisor_dir, "calibration")
    assert calibration["review_type"] == "judge.slice-vs-arch"
    assert (calibration["samples"], calibration["invocations"]) == (3, 1)
    assert calibration["pass"] == 3
    assert (calibration["score_min"], calibration["score_max"]) == (80.0, 86.0)

    (check,) = inspect_rows(supervisor_dir, "checks")
    assert (check["id"], check["standing"]) == (check_id, "vacuous")

    kinds = [str(change["kind"]) for change in _feed(supervisor_dir)]
    assert kinds.count("verdict_recorded") == 3
    assert kinds.count("check_recorded") == 1
