"""A real judge review ingested as samples under invocations, through the store."""

from __future__ import annotations

from pathlib import Path

import pytest
from cli_harness import await_condition, stop_running
from ingest_e2e_harness import (
    applied,
    ingest_artifact,
    ingest_ok,
    inspect_rows,
    start_with_node,
)
from review_fixtures import JUDGE_REVIEW_107, ROUND_1_PART_1

from amoeba.cli.main import ExitCode


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


def _ingest_sample(supervisor_dir: Path, node: str, invocation: str) -> str:
    result = ingest_artifact(
        supervisor_dir,
        node,
        JUDGE_REVIEW_107,
        "--judge-invocation-id",
        invocation,
    )
    assert result.returncode == ExitCode.OK, result.stderr
    return result.stdout.strip()


def test_a_judge_review_is_a_sample_under_its_invocation(
    supervisor_dir: Path, runs_dir: Path
) -> None:
    process, node = start_with_node(supervisor_dir, runs_dir)
    try:
        sample_id = _ingest_sample(supervisor_dir, node, "j1")
        await_condition(lambda: applied(supervisor_dir, sample_id), "the sample")
        (verdict,) = inspect_rows(supervisor_dir, "verdicts")
        assert verdict["id"] == sample_id
        assert verdict["judge_invocation_id"] == "j1"
        assert verdict["review_type"] == "judge.slice-vs-arch"
        assert verdict["verdict"] == "PASS"
        assert verdict["model"] == "claude-sonnet-5-5"
        assert verdict["standing"] == "unattested"
        (calibration,) = inspect_rows(supervisor_dir, "calibration")
        assert (calibration["score_min"], calibration["score_max"]) == (86.0, 86.0)
    finally:
        stop_running(supervisor_dir, process)


def test_two_invocations_are_two_samples_and_a_repeat_is_one(
    supervisor_dir: Path, runs_dir: Path
) -> None:
    process, node = start_with_node(supervisor_dir, runs_dir)
    try:
        first = _ingest_sample(supervisor_dir, node, "j1")
        second = _ingest_sample(supervisor_dir, node, "j2")
        repeat = _ingest_sample(supervisor_dir, node, "j1")
        assert repeat == first
        assert first != second
        await_condition(lambda: applied(supervisor_dir, first, second), "samples")
        verdicts = inspect_rows(supervisor_dir, "verdicts")
        assert sorted(str(v["judge_invocation_id"]) for v in verdicts) == ["j1", "j2"]
    finally:
        stop_running(supervisor_dir, process)


def test_an_ordinary_review_keeps_its_digest_id_and_id_overrides_the_sample_id(
    supervisor_dir: Path, runs_dir: Path
) -> None:
    process, node = start_with_node(supervisor_dir, runs_dir)
    try:
        plain = ingest_ok(supervisor_dir, node, ROUND_1_PART_1)
        chosen = ingest_artifact(
            supervisor_dir,
            node,
            JUDGE_REVIEW_107,
            "--judge-invocation-id",
            "j1",
            "--id",
            "chosen-id",
        )
        assert chosen.stdout.strip() == "chosen-id", chosen.stderr
        await_condition(lambda: applied(supervisor_dir, plain, "chosen-id"), "both")
        by_id = {str(v["id"]): v for v in inspect_rows(supervisor_dir, "verdicts")}
        assert by_id[plain]["judge_invocation_id"] is None
        assert by_id["chosen-id"]["judge_invocation_id"] == "j1"
    finally:
        stop_running(supervisor_dir, process)
