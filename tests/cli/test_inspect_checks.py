"""``amoeba inspect`` ``checks`` and ``calibration``, as subprocesses.

The generic listing tests in ``test_cli_inspect.py`` already run every listing
in both forms, stopped and running. This module covers what is specific to
these two: the pinned columns, the check standings, ``--node``, and the empty
project.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from cli_harness import await_running, run_cli, start_background
from evidence_harness import (
    PROJECT,
    check_input,
    seed_node,
    verdict_input,
)

from amoeba.cli.main import ExitCode
from amoeba.store import CheckOutcome, ReviewVerdict, Store

CHECK_ROWS = (
    # (id, outcome, examined_count, expected standing)
    ("c-pass", CheckOutcome.PASSED, 12, "passed"),
    ("c-fail", CheckOutcome.FAILED, 4, "failed"),
    ("c-vacuous-pass", CheckOutcome.PASSED, 0, "vacuous"),
    ("c-vacuous-fail", CheckOutcome.FAILED, 0, "vacuous"),
    ("c-unattested", CheckOutcome.PASSED, None, "unattested"),
    ("c-errored", CheckOutcome.ERRORED, 0, "errored"),
)


@pytest.fixture
def supervisor_dir(tmp_path: Path) -> Path:
    """A throwaway supervisor directory. Never the real one."""
    directory = tmp_path / "supervisor"
    directory.mkdir()
    return directory


@pytest.fixture
def empty_project(supervisor_dir: Path) -> Path:
    """A project store with a node and no checks and no samples."""
    with Store.open(supervisor_dir / f"{PROJECT}.sqlite3") as store:
        seed_node(store)
    return supervisor_dir


@pytest.fixture
def populated(supervisor_dir: Path) -> tuple[Path, str, str]:
    """Six checks on one node, one on another; two models' samples."""
    with Store.open(supervisor_dir / f"{PROJECT}.sqlite3") as store:
        node, other = seed_node(store), seed_node(store)
        for check_id, outcome, count, _ in CHECK_ROWS:
            store.record_check(
                check_input(check_id, node, outcome=outcome, examined_count=count),
                project_id=PROJECT,
            )
        store.record_check(check_input("c-other", other), project_id=PROJECT)
        for sample_id, invocation, model, verdict, score in (
            ("s1", "j1", "model-a", ReviewVerdict.PASS, 80.0),
            ("s2", "j2", "model-a", ReviewVerdict.CONCERNS, 60.0),
            ("s3", "j1", "model-b", ReviewVerdict.FAIL, None),
        ):
            store.record_verdict(
                verdict_input(
                    sample_id,
                    node,
                    judge_invocation_id=invocation,
                    model=model,
                    verdict=verdict,
                    score=score,
                ),
                project_id=PROJECT,
            )
    return supervisor_dir, node, other


def _inspect(supervisor_dir: Path, *arguments: str) -> tuple[int, str, str]:
    result = run_cli(["inspect", *arguments, "--project", PROJECT], supervisor_dir)
    return result.returncode, result.stdout, result.stderr


def _json(supervisor_dir: Path, *arguments: str) -> list[dict[str, object]]:
    code, stdout, stderr = _inspect(supervisor_dir, *arguments, "--json")
    assert code == ExitCode.OK, stderr
    rows: list[dict[str, object]] = json.loads(stdout)
    return rows


def test_checks_table_has_the_pinned_columns(
    populated: tuple[Path, str, str],
) -> None:
    supervisor_dir, _, _ = populated
    code, stdout, stderr = _inspect(supervisor_dir, "checks")
    assert code == ExitCode.OK, stderr
    assert stdout.splitlines()[0].split() == [
        "recorded_seq",
        "id",
        "node_id",
        "name",
        "outcome",
        "examined_count",
        "standing",
        "baseline_ref",
        "upstream_version",
    ]


def test_each_check_shows_the_standing_it_earns(
    populated: tuple[Path, str, str],
) -> None:
    supervisor_dir, node, _ = populated
    rows = _json(supervisor_dir, "checks", "--node", node)
    assert [(r["id"], r["standing"]) for r in rows] == [
        (check_id, standing) for check_id, _, _, standing in CHECK_ROWS
    ]
    by_id = {r["id"]: r for r in rows}
    assert by_id["c-unattested"]["examined_count"] is None
    assert by_id["c-vacuous-pass"]["outcome"] == "passed"
    assert by_id["c-pass"]["upstream_version"] == "1.2.3"


def test_checks_filter_by_node_and_json_carries_provenance(
    populated: tuple[Path, str, str],
) -> None:
    supervisor_dir, _, other = populated
    assert [r["id"] for r in _json(supervisor_dir, "checks", "--node", other)] == [
        "c-other"
    ]
    everything = _json(supervisor_dir, "checks")
    assert len(everything) == len(CHECK_ROWS) + 1
    assert everything[0]["source"] == "command_output"
    assert everything[0]["upstream"] == "context-forge"


def test_calibration_table_has_the_pinned_columns(
    populated: tuple[Path, str, str],
) -> None:
    supervisor_dir, _, _ = populated
    code, stdout, stderr = _inspect(supervisor_dir, "calibration")
    assert code == ExitCode.OK, stderr
    assert stdout.splitlines()[0].split() == [
        "review_type",
        "model",
        "samples",
        "invocations",
        "pass",
        "concerns",
        "fail",
        "unknown",
        "provider_failures",
        "score_min",
        "score_mean",
        "score_max",
    ]


def test_calibration_has_one_row_per_group(
    populated: tuple[Path, str, str],
) -> None:
    supervisor_dir, _, _ = populated
    rows = _json(supervisor_dir, "calibration")
    assert [(r["model"], r["samples"], r["invocations"]) for r in rows] == [
        ("model-a", 2, 2),
        ("model-b", 1, 1),
    ]
    first = rows[0]
    assert (first["pass"], first["concerns"], first["fail"]) == (1, 1, 0)
    assert (first["score_min"], first["score_mean"], first["score_max"]) == (
        60.0,
        70.0,
        80.0,
    )
    assert rows[1]["score_min"] is None


@pytest.mark.parametrize("listing", ["checks", "calibration"])
def test_an_empty_project_gives_no_rows_and_a_clean_exit(
    empty_project: Path, listing: str
) -> None:
    assert _json(empty_project, listing) == []
    code, _, stderr = _inspect(empty_project, listing)
    assert code == ExitCode.OK, stderr


@pytest.mark.parametrize("listing", ["checks", "calibration"])
def test_listings_work_while_the_process_holds_the_lock(
    populated: tuple[Path, str, str], tmp_path: Path, listing: str
) -> None:
    supervisor_dir, _, _ = populated
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    process = start_background(
        supervisor_dir, ["--sq-runs-dir", str(runs_dir), "--idle-interval", "0.05"]
    )
    try:
        await_running(supervisor_dir)
        assert _json(supervisor_dir, listing) != []
    finally:
        run_cli(["stop"], supervisor_dir)
        process.cleanup()
