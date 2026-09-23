"""The listings, and the envelope parser, against real submit() output.

Every file here is either written by the real ``submit()`` or derived from its
bytes — never a hand-written approximation of the format.
"""

from __future__ import annotations

import shutil
from datetime import UTC, datetime
from pathlib import Path

import pytest
from inbox_harness import (
    EXTRA_FIELDS,
    FIXTURE_SUBMISSION_ID,
    TRUNCATED,
    WRONG_VERSION,
    RealSubmission,
    write_real_submission,
)

from amoeba.inbox import failed, layout, pending, quarantined
from amoeba.inbox.envelope import EnvelopeError, parse_envelope
from amoeba.inbox.sidecars import AttemptsSidecar, ReasonSidecar
from amoeba.store import QuarantineReason

FAILED_AT = datetime(2026, 9, 23, 12, 0, tzinfo=UTC)


def _move(real: RealSubmission, destination: Path) -> Path:
    destination.mkdir(parents=True, exist_ok=True)
    return Path(shutil.move(real.path, destination / real.path.name))


# --------------------------------------------------------------------------
# The parser against real and damaged bytes
# --------------------------------------------------------------------------


def test_the_real_file_parses(real_submission: RealSubmission) -> None:
    envelope = parse_envelope(real_submission.content)

    assert envelope.id == FIXTURE_SUBMISSION_ID


def test_extra_unknown_fields_are_ignored(damaged_envelopes: dict[str, bytes]) -> None:
    envelope = parse_envelope(damaged_envelopes[EXTRA_FIELDS])

    assert envelope.id == FIXTURE_SUBMISSION_ID
    assert "unknown_payload_key" not in envelope.payload


@pytest.mark.parametrize(
    ("variant", "reason"),
    [
        (TRUNCATED, QuarantineReason.UNPARSEABLE_ENVELOPE),
        (WRONG_VERSION, QuarantineReason.UNKNOWN_ENVELOPE_VERSION),
    ],
)
def test_damaged_files_do_not_parse(
    damaged_envelopes: dict[str, bytes], variant: str, reason: QuarantineReason
) -> None:
    with pytest.raises(EnvelopeError) as caught:
        parse_envelope(damaged_envelopes[variant])

    assert caught.value.reason is reason


# --------------------------------------------------------------------------
# pending()
# --------------------------------------------------------------------------


def test_pending_lists_new_in_filename_order(supervisor_dir: Path) -> None:
    """Drain order is the filename's timestamp prefix, not write order."""
    written_first = write_real_submission(supervisor_dir, "a")
    written_second = write_real_submission(supervisor_dir, "b")
    earlier = written_second.path.with_name(layout.submission_filename(0, "b"))
    written_second.path.rename(earlier)

    assert [entry.path for entry in pending(supervisor_dir)] == [
        earlier,
        written_first.path,
    ]


def test_pending_reports_zero_attempts_without_a_counter(
    real_submission: RealSubmission,
) -> None:
    [entry] = pending(real_submission.supervisor_dir)

    assert entry.path == real_submission.path
    assert entry.attempts == 0
    assert entry.sidecar_error is None


def test_pending_reads_an_attempt_counter(real_submission: RealSubmission) -> None:
    layout.attempts_sidecar(real_submission.path).write_text(
        AttemptsSidecar(
            attempts=2, last_error="boom", last_failed_at=FAILED_AT
        ).model_dump_json()
    )

    [entry] = pending(real_submission.supervisor_dir)

    assert entry.attempts == 2


def test_a_stray_tmp_file_is_listed_nowhere(real_submission: RealSubmission) -> None:
    supervisor_dir = real_submission.supervisor_dir
    (layout.tmp_dir(supervisor_dir) / real_submission.path.name).write_bytes(b"{")

    assert [entry.path for entry in pending(supervisor_dir)] == [real_submission.path]
    assert quarantined(supervisor_dir) == []
    assert failed(supervisor_dir) == []


def test_listings_of_an_absent_inbox_are_empty(supervisor_dir: Path) -> None:
    assert pending(supervisor_dir) == []
    assert quarantined(supervisor_dir) == []
    assert failed(supervisor_dir) == []


# --------------------------------------------------------------------------
# quarantined() and failed()
# --------------------------------------------------------------------------


def test_quarantined_surfaces_the_recorded_reason(
    real_submission: RealSubmission,
) -> None:
    moved = _move(
        real_submission, layout.quarantine_dir(real_submission.supervisor_dir)
    )
    layout.reason_sidecar(moved).write_text(
        ReasonSidecar(
            reason=QuarantineReason.NO_STORE_FOR_PROJECT,
            detail="no store for demo",
            quarantined_at=FAILED_AT,
        ).model_dump_json()
    )

    [entry] = quarantined(real_submission.supervisor_dir)

    assert entry.path == moved
    assert entry.reason is QuarantineReason.NO_STORE_FOR_PROJECT
    assert entry.detail == "no store for demo"
    assert entry.sidecar_error is None


def test_failed_surfaces_the_count_and_last_error(
    real_submission: RealSubmission,
) -> None:
    moved = _move(real_submission, layout.failed_dir(real_submission.supervisor_dir))
    layout.attempts_sidecar(moved).write_text(
        AttemptsSidecar(
            attempts=3,
            last_error="database disk image is malformed",
            last_failed_at=FAILED_AT,
        ).model_dump_json()
    )

    [entry] = failed(real_submission.supervisor_dir)

    assert entry.attempts == 3
    assert entry.last_error == "database disk image is malformed"
    assert entry.last_failed_at == FAILED_AT


@pytest.mark.parametrize("sidecar_content", [None, b"{not json"])
def test_a_missing_or_damaged_sidecar_is_reported_not_raised(
    real_submission: RealSubmission, sidecar_content: bytes | None
) -> None:
    supervisor_dir = real_submission.supervisor_dir
    in_quarantine = _move(real_submission, layout.quarantine_dir(supervisor_dir))
    in_failed = layout.failed_dir(supervisor_dir) / in_quarantine.name
    in_failed.parent.mkdir(parents=True)
    shutil.copy(in_quarantine, in_failed)
    if sidecar_content is not None:
        layout.reason_sidecar(in_quarantine).write_bytes(sidecar_content)
        layout.attempts_sidecar(in_failed).write_bytes(sidecar_content)

    [quarantined_entry] = quarantined(supervisor_dir)
    [failed_entry] = failed(supervisor_dir)

    assert quarantined_entry.reason is None
    assert quarantined_entry.sidecar_error is not None
    assert failed_entry.attempts is None
    assert failed_entry.sidecar_error is not None
