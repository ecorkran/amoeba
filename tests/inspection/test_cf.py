"""``amoeba inspect`` ``cf-links`` and ``cf-snapshots``, as subprocesses.

The generic listing tests in ``test_cli_inspect.py`` already run every listing in
both forms, stopped and running. This module covers what is specific to these
two: the pinned columns, each outcome, text against ``--json``, and that no
other flags are accepted.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from cf_harness import failure, observed
from cli_harness import run_cli

from amoeba.cli.main import ExitCode
from amoeba.store import CFSnapshotOutcome, Store, SubmissionKind
from amoeba.store.inbox_models import LINK_CF_PROJECT_ID

PROJECT = "demo"
CF_ID = "project_1_abc"

CHANGED = [
    {"worktree_id": "wt_1", "field": "developmentPhase", "from": "a", "to": "b"},
    {"worktree_id": "wt_1", "field": "activeSlice", "from": "x", "to": "y"},
    {"worktree_id": None, "field": "developmentPhase", "from": "a", "to": "b"},
]


@pytest.fixture
def supervisor_dir(tmp_path: Path) -> Path:
    """A throwaway supervisor directory. Never the real one."""
    directory = tmp_path / "supervisor"
    directory.mkdir()
    return directory


@pytest.fixture
def empty_project(supervisor_dir: Path) -> Path:
    with Store.open(supervisor_dir / f"{PROJECT}.sqlite3"):
        pass
    return supervisor_dir


@pytest.fixture
def populated(supervisor_dir: Path) -> Path:
    """Two links, and one snapshot of each outcome for the first."""
    with Store.open(supervisor_dir / f"{PROJECT}.sqlite3") as store:
        for index, cf_id in enumerate((CF_ID, "project_2_def")):
            store.apply_submission(
                submission_id=f"link-{index}",
                project_id=PROJECT,
                kind=SubmissionKind.LINK_CF_PROJECT,
                submitted_by="pm",
                submitted_at=datetime(2026, 10, 16, tzinfo=UTC),
                payload={LINK_CF_PROJECT_ID: cf_id},
            )
        store.record_cf_snapshot(observed(PROJECT, CF_ID, changed=CHANGED))
        for outcome in CFSnapshotOutcome:
            if outcome is not CFSnapshotOutcome.OBSERVED:
                store.record_cf_snapshot(
                    failure(PROJECT, CF_ID, outcome, f"{outcome.value} detail")
                )
    return supervisor_dir


def _inspect(supervisor_dir: Path, *arguments: str) -> tuple[int, str, str]:
    result = run_cli(["inspect", *arguments, "--project", PROJECT], supervisor_dir)
    return result.returncode, result.stdout, result.stderr


def _json(supervisor_dir: Path, *arguments: str) -> list[dict[str, object]]:
    code, stdout, stderr = _inspect(supervisor_dir, *arguments, "--json")
    assert code == ExitCode.OK, stderr
    rows: list[dict[str, object]] = json.loads(stdout)
    return rows


@pytest.mark.parametrize("listing", ["cf-links", "cf-snapshots"])
def test_an_empty_project_lists_nothing(empty_project: Path, listing: str) -> None:
    code, stdout, stderr = _inspect(empty_project, listing)
    assert code == ExitCode.OK, stderr
    assert stdout.strip() == "(none)"
    assert _json(empty_project, listing) == []


def test_cf_links_has_the_pinned_columns_and_link_order(populated: Path) -> None:
    code, stdout, stderr = _inspect(populated, "cf-links")
    assert code == ExitCode.OK, stderr
    assert stdout.splitlines()[0].split() == ["cf_project_id", "linked_at"]
    assert [r["cf_project_id"] for r in _json(populated, "cf-links")] == [
        CF_ID,
        "project_2_def",
    ]


def test_cf_snapshots_has_the_pinned_columns(populated: Path) -> None:
    code, stdout, stderr = _inspect(populated, "cf-snapshots")
    assert code == ExitCode.OK, stderr
    assert stdout.splitlines()[0].split() == [
        "id",
        "observed_at",
        "cf_project_id",
        "outcome",
        "changed_fields",
        "detail",
        "cf_updated_at",
    ]


def test_each_outcome_appears_with_its_detail(populated: Path) -> None:
    rows = _json(populated, "cf-snapshots")
    assert [r["outcome"] for r in rows] == [o.value for o in CFSnapshotOutcome]
    failures = [r for r in rows if r["outcome"] != "observed"]
    assert all(r["detail"] == f"{r['outcome']} detail" for r in failures)
    assert all(r["changed"] is None and r["state"] is None for r in failures)


def test_text_summarizes_the_fields_and_json_carries_the_full_changes(
    populated: Path,
) -> None:
    code, stdout, _ = _inspect(populated, "cf-snapshots")
    assert code == ExitCode.OK
    first = stdout.splitlines()[2]
    assert "developmentPhase, activeSlice" in first  # distinct, in order
    assert "wt_1" not in first
    [observed_row, *_] = _json(populated, "cf-snapshots")
    assert observed_row["changed"] == CHANGED
    assert observed_row["state"] == {"project": {"name": "demo"}, "worktrees": {}}


@pytest.mark.parametrize("listing", ["cf-links", "cf-snapshots"])
def test_no_flag_other_than_project_is_accepted(populated: Path, listing: str) -> None:
    for extra in ("--node", "--outcome", "--cf-project-id"):
        result = run_cli(
            ["inspect", listing, "--project", PROJECT, extra, "x"], populated
        )
        assert result.returncode != ExitCode.OK
