"""The replay helpers: a recording comes back as recorded, a failure fails."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from cf_fixtures import (
    DEFAULT_WORKTREE,
    FIXTURES,
    OUTSIDE_ANY_PROJECT,
    fake_cf_run,
    fixture_document,
    fixture_text,
    write_fake_cf,
)


def test_fake_run_returns_the_recorded_text() -> None:
    completed = fake_cf_run(DEFAULT_WORKTREE)(["cf", "get", "--json"])

    assert completed.returncode == 0
    assert completed.stdout == fixture_text(DEFAULT_WORKTREE)


def test_fake_run_puts_the_not_found_document_on_stderr() -> None:
    completed = fake_cf_run(OUTSIDE_ANY_PROJECT)(["cf", "get", "--json"])

    assert completed.returncode != 0
    assert completed.stdout == ""
    assert completed.stderr == fixture_text(OUTSIDE_ANY_PROJECT)


def test_every_recording_parses_and_the_project_recordings_share_an_id() -> None:
    names = sorted(path.stem for path in FIXTURES.glob("*.json"))
    assert len(names) == 4
    documents = {name: fixture_document(name) for name in names}

    ids = {doc["id"] for name, doc in documents.items() if name != OUTSIDE_ANY_PROJECT}
    assert len(ids) == 1
    assert documents[OUTSIDE_ANY_PROJECT]["code"] == "PROJECT_NOT_FOUND"


def test_fake_run_failure_mode_prints_no_json() -> None:
    completed = fake_cf_run(None)(["cf", "get", "--json"])

    assert completed.returncode != 0
    assert completed.stdout == ""


def test_script_in_failure_mode_exits_nonzero(tmp_path: Path) -> None:
    script = write_fake_cf(tmp_path / "bin", None)

    assert subprocess.run([str(script)], capture_output=True).returncode != 0


def test_script_replays_a_recording(tmp_path: Path) -> None:
    script = write_fake_cf(tmp_path / "bin", DEFAULT_WORKTREE)

    completed = subprocess.run(
        [str(script)], capture_output=True, text=True, env=os.environ
    )

    assert completed.returncode == 0
    assert completed.stdout == fixture_text(DEFAULT_WORKTREE)


def test_script_replays_the_error_document_on_stderr(tmp_path: Path) -> None:
    script = write_fake_cf(tmp_path / "bin", OUTSIDE_ANY_PROJECT)

    completed = subprocess.run([str(script)], capture_output=True, text=True)

    assert completed.returncode != 0
    assert completed.stderr == fixture_text(OUTSIDE_ANY_PROJECT)
