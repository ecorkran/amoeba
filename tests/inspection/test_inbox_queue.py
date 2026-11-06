"""The ``inbox`` listing's last column, ``queue``, and the program inbox's rows."""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

from inbox_harness import write_real_submission
from program_harness import program_payload

from amoeba.inbox import layout, submit_program
from amoeba.inbox.sidecars import AttemptsSidecar, ReasonSidecar
from amoeba.inspection import LISTINGS_BY_NAME, ListingRequest, read_listing
from amoeba.inspection.inbox import INBOX_COLUMNS
from amoeba.store import ProgramSubmissionKind, QuarantineReason
from amoeba.store.paths import program_dir

REQUEST = ListingRequest(project_id=None, options={}, compact=False)
FAILED_AT = datetime(2026, 11, 5, 12, 0, tzinfo=UTC)


def _rows(supervisor_dir: Path) -> list[dict[str, object]]:
    return read_listing("inbox", REQUEST, supervisor_dir).rows


def _program_file(supervisor_dir: Path, submission_id: str) -> Path:
    submit_program(
        kind=ProgramSubmissionKind.REGISTER_PROGRAM,
        payload=program_payload(),
        submitted_by="tester",
        submission_id=submission_id,
        store_dir=supervisor_dir,
    )
    [path] = [
        candidate
        for candidate in layout.submission_files(
            layout.new_dir(program_dir(supervisor_dir))
        )
        if candidate.name.endswith(f"-{submission_id}.json")
    ]
    return path


def _move(path: Path, directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    return Path(shutil.move(path, directory / path.name))


def test_queue_is_the_last_column_and_the_earlier_ones_keep_their_positions() -> None:
    assert INBOX_COLUMNS == ("state", "file", "attempts", "reason", "problem", "queue")
    assert LISTINGS_BY_NAME["inbox"].columns == INBOX_COLUMNS


def test_project_rows_are_unchanged_but_for_the_key(supervisor_dir: Path) -> None:
    real = write_real_submission(supervisor_dir)

    [row] = _rows(supervisor_dir)

    assert row == {
        "state": "new",
        "file": real.path.name,
        "attempts": 0,
        "reason": "",
        "problem": "",
        "queue": "project",
    }


def test_a_program_file_in_new_is_listed_as_the_program_queue(
    supervisor_dir: Path,
) -> None:
    path = _program_file(supervisor_dir, "pending-1")

    [row] = _rows(supervisor_dir)

    assert (row["state"], row["file"], row["queue"]) == (
        "new",
        path.name,
        "program",
    )


def test_a_program_quarantine_shows_its_reason(supervisor_dir: Path) -> None:
    path = _program_file(supervisor_dir, "quarantined-1")
    destination = _move(path, layout.quarantine_dir(program_dir(supervisor_dir)))
    layout.reason_sidecar(destination).write_text(
        ReasonSidecar(
            reason=QuarantineReason.INVALID_PAYLOAD,
            detail="concept_path: field required",
            quarantined_at=FAILED_AT,
        ).model_dump_json()
    )

    [row] = _rows(supervisor_dir)

    assert (row["state"], row["queue"]) == ("quarantine", "program")
    assert row["reason"] == "invalid_payload"
    assert "concept_path" in str(row["problem"])


def test_a_program_file_in_failed_shows_its_attempts(supervisor_dir: Path) -> None:
    path = _program_file(supervisor_dir, "failed-1")
    destination = _move(path, layout.failed_dir(program_dir(supervisor_dir)))
    layout.attempts_sidecar(destination).write_text(
        AttemptsSidecar(
            attempts=3, last_error="StoreCorruptError: x", last_failed_at=FAILED_AT
        ).model_dump_json()
    )

    [row] = _rows(supervisor_dir)

    assert (row["state"], row["attempts"], row["queue"]) == ("failed", 3, "program")
    assert "StoreCorruptError" in str(row["problem"])


def test_both_inboxes_list_together_project_rows_first(supervisor_dir: Path) -> None:
    _program_file(supervisor_dir, "program-1")
    write_real_submission(supervisor_dir)

    rows = _rows(supervisor_dir)

    assert [row["queue"] for row in rows] == ["project", "program"]
    assert all(list(row) == list(INBOX_COLUMNS) for row in rows)
    json.dumps(rows)  # the rows stay JSON-serializable for --json and the server
