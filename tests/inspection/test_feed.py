"""``inspect watches`` and ``inspect detections`` through the real CLI.

States are staged by writing store rows directly; no tenant runs.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from cli_harness import run_cli
from evidence_harness import verdict_input
from sq_run_fixtures import sq_run_parameters

from amoeba.cli.main import ExitCode
from amoeba.inspection.feed import DETECTION_COLUMNS, WATCH_COLUMNS, WatchState
from amoeba.store import (
    CommandKind,
    DetectionInput,
    DetectionOutcome,
    NodeKind,
    Store,
    SubmissionKind,
)
from amoeba.store.inbox_models import WATCH_ACTIVE, WATCH_REVIEWS_DIR
from amoeba.store.paths import project_store_path

PROJECT = "demo"
CALM = "calm"
SUBMITTED_AT = datetime(2026, 10, 15, tzinfo=UTC)


def _open(supervisor_dir: Path, project_id: str) -> Store:
    return Store.open(project_store_path(supervisor_dir, project_id))


def _watch(store: Store, project_id: str, directory: Path, *, active: bool) -> None:
    store.apply_submission(
        submission_id=f"watch-{directory.name}-{active}",
        project_id=project_id,
        kind=SubmissionKind.WATCH_REVIEWS,
        submitted_by="test",
        submitted_at=SUBMITTED_AT,
        payload={WATCH_REVIEWS_DIR: str(directory), WATCH_ACTIVE: active},
    )


def _inspect(
    supervisor_dir: Path, project_id: str, *arguments: str
) -> list[dict[str, object]]:
    result = run_cli(
        ["inspect", *arguments, "--project", project_id, "--json"], supervisor_dir
    )
    assert result.returncode == ExitCode.OK, result.stderr
    rows: list[dict[str, object]] = json.loads(result.stdout)
    return rows


@pytest.fixture
def staged(supervisor_dir: Path, tmp_path: Path) -> Iterator[dict[str, Path]]:
    """One watch per state. ``demo`` has an open review entry; ``calm`` does not."""
    present = {name: tmp_path / name for name in ("inactive", "pending", "busy", "ok")}
    for directory in present.values():
        directory.mkdir()
    missing = tmp_path / "missing"

    with _open(supervisor_dir, PROJECT) as store:
        _watch(store, PROJECT, present["inactive"], active=False)
        _watch(store, PROJECT, missing, active=True)
        _watch(store, PROJECT, present["pending"], active=True)
        _watch(store, PROJECT, present["busy"], active=True)
        store.baseline_watch(PROJECT, str(present["busy"]), ())
        node = store.create_node(project_id=PROJECT, kind=NodeKind.SLICE, title="s")
        store.journal_issue(
            node.id,
            kind=CommandKind.SQ_RUN,
            parameters=sq_run_parameters({"pipeline": "p", "params": {}}),
        )
    with _open(supervisor_dir, CALM) as store:
        _watch(store, CALM, present["ok"], active=True)
        store.baseline_watch(CALM, str(present["ok"]), ())
    yield {**present, "missing": missing}


def _states(supervisor_dir: Path, project_id: str) -> dict[str, object]:
    return {
        Path(str(row["reviews_dir"])).name: row["state"]
        for row in _inspect(supervisor_dir, project_id, "watches")
    }


def test_watches_shows_every_state(
    supervisor_dir: Path, staged: dict[str, Path]
) -> None:
    assert _states(supervisor_dir, PROJECT) == {
        "inactive": WatchState.INACTIVE.value,
        # Unbaselined and in a deferred project: unreachable wins over both.
        "missing": WatchState.UNREACHABLE.value,
        "pending": WatchState.BASELINE_PENDING.value,
        "busy": WatchState.DEFERRED.value,
    }
    assert _states(supervisor_dir, CALM) == {"ok": WatchState.OK.value}


def test_watches_json_has_the_table_columns(
    supervisor_dir: Path, staged: dict[str, Path]
) -> None:
    rows = _inspect(supervisor_dir, PROJECT, "watches")
    assert all(tuple(row) == WATCH_COLUMNS for row in rows)
    table = run_cli(["inspect", "watches", "--project", PROJECT], supervisor_dir)
    assert table.stdout.splitlines()[0].split() == list(WATCH_COLUMNS)


# --------------------------------------------------------------------------
# detections
# --------------------------------------------------------------------------


@pytest.fixture
def ledger(supervisor_dir: Path) -> str:
    """One row per outcome; the ``unattributed`` one carries a record id."""
    with _open(supervisor_dir, PROJECT) as store:
        for outcome in DetectionOutcome:
            store.record_detection(
                DetectionInput(
                    project_id=PROJECT,
                    path=f"/r/{outcome.value}.md",
                    digest="d",
                    outcome=outcome,
                    record_id=(
                        "rec-1" if outcome is DetectionOutcome.UNATTRIBUTED else None
                    ),
                )
            )
    return "rec-1"


def test_detections_lists_every_outcome_in_order(
    supervisor_dir: Path, ledger: str
) -> None:
    rows = _inspect(supervisor_dir, PROJECT, "detections")
    assert [row["outcome"] for row in rows] == [o.value for o in DetectionOutcome]
    assert all(tuple(row) == DETECTION_COLUMNS for row in rows)


def test_detections_filters_by_outcome(supervisor_dir: Path, ledger: str) -> None:
    rows = _inspect(supervisor_dir, PROJECT, "detections", "--outcome", "unattributed")
    assert [row["path"] for row in rows] == ["/r/unattributed.md"]


def test_recorded_since_flips_once_the_verdict_exists(
    supervisor_dir: Path, ledger: str
) -> None:
    def unattributed() -> dict[str, object]:
        [row] = _inspect(
            supervisor_dir, PROJECT, "detections", "--outcome", "unattributed"
        )
        return row

    assert unattributed()["recorded_since"] is False
    with _open(supervisor_dir, PROJECT) as store:
        node = store.create_node(project_id=PROJECT, kind=NodeKind.SLICE, title="s")
        store.record_verdict(verdict_input(ledger, node.id), project_id=PROJECT)
    assert unattributed()["recorded_since"] is True
