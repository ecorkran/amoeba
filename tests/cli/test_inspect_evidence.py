"""``amoeba inspect verdicts`` and ``amoeba inspect findings``, as real subprocesses.

The generic listing tests in ``test_cli_inspect.py`` already run every listing
in both forms, stopped and running. This module covers what is specific to
these two: the pinned columns, ``--node``, provenance in JSON, and the
``--verdict`` header, tags, and errors.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from cli_harness import await_running, run_cli, start_background
from evidence_harness import (
    PROJECT,
    finding,
    provider_failure,
    seed_node,
    verdict_input,
)

from amoeba.cli.main import ExitCode
from amoeba.store import Store

_KEPT = finding("The flag rule is unspecified", "tasks-2.md:119-163")
_KEPT_MOVED = finding("The flag rule is unspecified.", "tasks-2.md:218-240")
_DROPPED = finding("No commit checkpoint", "tasks-1.md:40")
_ADDED = finding("A brand new problem", "tasks-2.md:10")


@pytest.fixture
def supervisor_dir(tmp_path: Path) -> Path:
    """A throwaway supervisor directory. Never the real one."""
    directory = tmp_path / "supervisor"
    directory.mkdir()
    return directory


@pytest.fixture
def nodes(supervisor_dir: Path) -> tuple[str, str]:
    """Two rounds and a provider failure on one node; one review on another."""
    with Store.open(supervisor_dir / f"{PROJECT}.sqlite3") as store:
        node, other = seed_node(store), seed_node(store)
        for verdict in (
            verdict_input("r1", node, _KEPT, _DROPPED),
            provider_failure("r2", node),
            verdict_input("r3", node, _ADDED, _KEPT_MOVED),
            verdict_input("o1", other, _ADDED),
        ):
            store.record_verdict(verdict, project_id=PROJECT)
    return node, other


def _inspect(supervisor_dir: Path, *arguments: str) -> tuple[int, str, str]:
    result = run_cli(["inspect", *arguments, "--project", PROJECT], supervisor_dir)
    return result.returncode, result.stdout, result.stderr


def _json(supervisor_dir: Path, *arguments: str) -> list[dict[str, object]]:
    code, stdout, stderr = _inspect(supervisor_dir, *arguments, "--json")
    assert code == ExitCode.OK, stderr
    rows: list[dict[str, object]] = json.loads(stdout)
    return rows


def test_verdicts_table_has_the_pinned_columns(
    supervisor_dir: Path, nodes: tuple[str, str]
) -> None:
    code, stdout, stderr = _inspect(supervisor_dir, "verdicts")
    assert code == ExitCode.OK, stderr
    assert stdout.splitlines()[0].split() == [
        "recorded_seq",
        "id",
        "node_id",
        "review_type",
        "model",
        "verdict",
        "standing",
        "upstream_version",
    ]
    assert "provider_failure" in stdout


def test_verdicts_filter_by_node_and_carry_provenance(
    supervisor_dir: Path, nodes: tuple[str, str]
) -> None:
    node, other = nodes
    assert [r["id"] for r in _json(supervisor_dir, "verdicts")] == [
        "r1",
        "r2",
        "r3",
        "o1",
    ]
    assert [r["id"] for r in _json(supervisor_dir, "verdicts", "--node", other)] == [
        "o1"
    ]
    for row in _json(supervisor_dir, "verdicts", "--node", node):
        assert row["upstream"] == "squadron"
        assert row["upstream_version"] == "0.14.0"
        assert row["source"] == "artifact_frontmatter"
        assert row["recorded_at"]
        assert "source_path" in row


def test_findings_without_verdict_is_one_row_per_key(
    supervisor_dir: Path, nodes: tuple[str, str]
) -> None:
    node, _ = nodes
    rows = _json(supervisor_dir, "findings", "--node", node)
    assert len(rows) == 3
    kept = next(r for r in rows if r["summary"] == _KEPT_MOVED.summary)
    assert (kept["times_seen"], kept["first_verdict_id"]) == (2, "r1")


def test_findings_for_a_verdict_names_the_previous_review_and_tags(
    supervisor_dir: Path, nodes: tuple[str, str]
) -> None:
    code, stdout, stderr = _inspect(supervisor_dir, "findings", "--verdict", "r3")
    assert code == ExitCode.OK, stderr
    assert stdout.splitlines()[0] == "verdict r3: previous review r1"

    rows = _json(supervisor_dir, "findings", "--verdict", "r3")
    assert [(r["change"], r["summary"]) for r in rows] == [
        ("new", _ADDED.summary),
        ("recurring", _KEPT_MOVED.summary),
        ("gone", _DROPPED.summary),
    ]
    assert {r["previous_verdict_id"] for r in rows} == {"r1"}


def test_findings_for_a_provider_failure_is_not_comparable(
    supervisor_dir: Path, nodes: tuple[str, str]
) -> None:
    code, stdout, _ = _inspect(supervisor_dir, "findings", "--verdict", "r2")
    assert code == ExitCode.OK
    assert stdout.splitlines()[0] == "verdict r2: not comparable"


def test_an_unknown_verdict_is_an_error(
    supervisor_dir: Path, nodes: tuple[str, str]
) -> None:
    code, stdout, stderr = _inspect(supervisor_dir, "findings", "--verdict", "nope")
    assert code != ExitCode.OK
    assert "nope" in stderr
    assert stdout == ""


@pytest.fixture
def running(
    supervisor_dir: Path, tmp_path: Path, nodes: tuple[str, str]
) -> Iterator[None]:
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    process = start_background(
        supervisor_dir, ["--sq-runs-dir", str(runs_dir), "--idle-interval", "0.05"]
    )
    try:
        await_running(supervisor_dir)
        yield
    finally:
        run_cli(["stop"], supervisor_dir)
        process.cleanup()


def test_both_listings_work_while_the_process_runs(
    supervisor_dir: Path, running: None
) -> None:
    assert len(_json(supervisor_dir, "verdicts")) == 4
    assert len(_json(supervisor_dir, "findings", "--verdict", "r3")) == 3
