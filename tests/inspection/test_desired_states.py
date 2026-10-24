"""``amoeba inspect desired-states``: the columns, the unset values, both forms."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from cli_harness import run_cli
from routing_helpers import submit_intent

from amoeba.cli.main import ExitCode
from amoeba.inspection import LISTINGS_BY_NAME, desired_states
from amoeba.inspection.desired_states import DESIRED_STATE_COLUMNS, PROJECT_TARGET
from amoeba.runner.intent.vocabulary import TargetKind
from amoeba.store import (
    AcknowledgmentOutcome,
    NodeKind,
    SetDesiredState,
    Store,
)

PROJECT = "demo"
LISTING = "desired-states"


def _set(store: Store, change: SetDesiredState) -> str:
    message_id = submit_intent(store, f"sub-{change.node_id}")
    store.acknowledge_message(
        message_id,
        acknowledged_by="runner",
        outcome=AcknowledgmentOutcome.APPLIED,
        desired_state=change,
    )
    return message_id


@pytest.fixture
def supervisor_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "supervisor"
    directory.mkdir()
    return directory


@pytest.fixture
def seeded(supervisor_dir: Path) -> dict[str, str]:
    """A project row, a node row with ``until``, and a hold-only node row."""
    with Store.open(supervisor_dir / f"{PROJECT}.sqlite3") as store:
        driven = store.create_node(project_id=PROJECT, kind=NodeKind.SLICE, title="a")
        held = store.create_node(project_id=PROJECT, kind=NodeKind.SLICE, title="b")
        return {
            "project": _set(store, SetDesiredState(drive=True)),
            "driven": driven.id,
            "held": held.id,
            "driven_message": _set(
                store,
                SetDesiredState(
                    node_id=driven.id, drive=True, drive_until_step="tasks"
                ),
            ),
            "held_message": _set(store, SetDesiredState(node_id=held.id, hold=True)),
        }


def _json(supervisor_dir: Path) -> list[dict[str, object]]:
    result = run_cli(
        ["inspect", LISTING, "--project", PROJECT, "--json"], supervisor_dir
    )
    assert result.returncode == ExitCode.OK, result.stderr
    rows: list[dict[str, object]] = json.loads(result.stdout)
    return rows


def test_the_listing_declares_its_columns() -> None:
    assert LISTING in LISTINGS_BY_NAME
    assert LISTINGS_BY_NAME[LISTING].columns == DESIRED_STATE_COLUMNS
    assert DESIRED_STATE_COLUMNS == (
        "target",
        "drive",
        "until",
        "hold",
        "message_id",
        "updated_at",
    )


def test_each_row_shows_its_settings_and_unset_values_are_empty(
    supervisor_dir: Path, seeded: dict[str, str]
) -> None:
    by_target = {row["target"]: row for row in _json(supervisor_dir)}

    assert by_target[PROJECT_TARGET]["drive"] == "true"
    assert (by_target[PROJECT_TARGET]["until"], by_target[PROJECT_TARGET]["hold"]) == (
        "",
        "",
    )
    assert by_target[PROJECT_TARGET]["message_id"] == seeded["project"]
    driven = by_target[seeded["driven"]]
    assert (driven["drive"], driven["until"], driven["hold"]) == ("true", "tasks", "")
    held = by_target[seeded["held"]]
    assert (held["drive"], held["until"], held["hold"]) == ("", "", "true")
    assert held["message_id"] == seeded["held_message"]


def test_the_project_row_comes_first_and_the_text_form_has_the_same_columns(
    supervisor_dir: Path, seeded: dict[str, str]
) -> None:
    targets = [str(row["target"]) for row in _json(supervisor_dir)]
    assert targets[0] == PROJECT_TARGET
    assert targets[1:] == sorted(targets[1:])
    result = run_cli(["inspect", LISTING, "--project", PROJECT], supervisor_dir)
    assert result.returncode == ExitCode.OK, result.stderr
    assert result.stdout.splitlines()[0].split() == list(DESIRED_STATE_COLUMNS)


def test_an_empty_project_returns_no_rows(supervisor_dir: Path) -> None:
    with Store.open(supervisor_dir / f"{PROJECT}.sqlite3"):
        pass
    assert _json(supervisor_dir) == []


def test_the_listing_imports_nothing_from_the_runner() -> None:
    source = Path(desired_states.__file__).read_text(encoding="utf-8")
    assert "amoeba.runner" not in source


def test_help_runs(supervisor_dir: Path) -> None:
    result = run_cli(["inspect", LISTING, "--help"], supervisor_dir)
    assert result.returncode == ExitCode.OK, result.stderr


def test_the_project_label_matches_the_runner_target_kind() -> None:
    # The listing may not import the Runner, so the label is stated here once more.
    assert PROJECT_TARGET == TargetKind.PROJECT.value
