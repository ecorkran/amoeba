"""InboxTenant: the apply loop, the quarantine ladder, and the attempt counter.

Driven in-process through ``LocalHost`` — real stores, real files, the real
tick — so every branch is reachable without a subprocess. The full-process
behavior (restarts, a running ``amoeba start``) is covered separately against
the real host.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest
from inbox_harness import (
    FIXTURE_SUBMISSION_ID,
    TRUNCATED,
    WRONG_VERSION,
    RealSubmission,
)
from local_host_harness import LocalHost

from amoeba.inbox import failed, layout, pending, quarantined, submit
from amoeba.process.inbox_tenant import InboxTenant
from amoeba.process.settings import ProcessSettings
from amoeba.store import (
    QuarantineReason,
    StorePermissionError,
    SubmissionKind,
    SubmissionOutcome,
)
from amoeba.store.inbox_models import INTENT_BODY
from amoeba.store.paths import STORE_FILE_SUFFIX

PROJECT = "demo"


def _submit_intent(supervisor_dir: Path, submission_id: str | None = None) -> str:
    return submit(
        project_id=PROJECT,
        kind=SubmissionKind.INTENT,
        payload={INTENT_BODY: {"want": "x"}},
        submitted_by="tester",
        submission_id=submission_id,
        store_dir=supervisor_dir,
    )


# --------------------------------------------------------------------------
# Smoke: the three claims of the apply loop
# --------------------------------------------------------------------------


def test_an_intent_applies_and_its_file_is_deleted(
    supervisor_dir: Path, local_host: LocalHost
) -> None:
    store = local_host.open_project(PROJECT)
    submission_id = _submit_intent(supervisor_dir)

    assert InboxTenant(supervisor_dir).tick(local_host) is True

    record = store.submission(submission_id)
    assert record is not None and record.outcome is SubmissionOutcome.APPLIED
    assert [message.submission_id for message in store.pending_intents(PROJECT)] == [
        submission_id
    ]
    assert pending(supervisor_dir) == []


def test_a_tick_handles_at_most_the_batch_size(
    supervisor_dir: Path, local_host: LocalHost
) -> None:
    local_host.open_project(PROJECT)
    local_host.settings = ProcessSettings(inbox_batch_size=2)
    for _ in range(5):
        _submit_intent(supervisor_dir)

    InboxTenant(supervisor_dir).tick(local_host)

    assert len(pending(supervisor_dir)) == 3


def test_a_tick_stops_early_when_stop_is_requested(
    supervisor_dir: Path, local_host: LocalHost
) -> None:
    local_host.open_project(PROJECT)
    _submit_intent(supervisor_dir)
    local_host.stop_requested = True

    assert InboxTenant(supervisor_dir).tick(local_host) is False
    assert len(pending(supervisor_dir)) == 1


def test_an_empty_inbox_reports_no_work(
    supervisor_dir: Path, local_host: LocalHost
) -> None:
    assert InboxTenant(supervisor_dir).tick(local_host) is False


# --------------------------------------------------------------------------
# Replay and D2
# --------------------------------------------------------------------------


def test_a_file_restored_after_apply_replays_as_a_no_op(
    supervisor_dir: Path, local_host: LocalHost, real_submission: RealSubmission
) -> None:
    store = local_host.open_project(PROJECT)
    tenant = InboxTenant(supervisor_dir)
    tenant.tick(local_host)

    real_submission.path.write_bytes(real_submission.content)
    assert tenant.tick(local_host) is True

    assert len(store.submissions(PROJECT)) == 1
    assert len(store.pending_intents(PROJECT)) == 1
    assert pending(supervisor_dir) == []


def test_a_reused_id_with_different_content_keeps_the_first_and_warns(
    supervisor_dir: Path,
    local_host: LocalHost,
    real_submission: RealSubmission,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """First wins, logged at WARNING — not an error: it may be a retry."""
    store = local_host.open_project(PROJECT)
    tenant = InboxTenant(supervisor_dir)
    tenant.tick(local_host)
    submit(
        project_id=PROJECT,
        kind=SubmissionKind.CREATE_PROJECT,
        payload={},
        submitted_by="someone-else",
        submission_id=FIXTURE_SUBMISSION_ID,
        store_dir=supervisor_dir,
    )

    with caplog.at_level(logging.WARNING, logger="amoeba.process.inbox_tenant"):
        tenant.tick(local_host)

    [record] = store.submissions(PROJECT)
    assert record.kind is SubmissionKind.INTENT
    assert [
        record.levelno
        for record in caplog.records
        if "reused with different content" in record.getMessage()
    ] == [logging.WARNING]
    assert pending(supervisor_dir) == []


# --------------------------------------------------------------------------
# The quarantine ladder
# --------------------------------------------------------------------------


def _bad_files(
    real: RealSubmission, damaged: dict[str, bytes]
) -> dict[QuarantineReason, bytes]:
    """One file per quarantine reason, all derived from real submit() bytes."""
    decoded = json.loads(real.content)
    return {
        QuarantineReason.UNPARSEABLE_ENVELOPE: damaged[TRUNCATED],
        QuarantineReason.UNKNOWN_ENVELOPE_VERSION: damaged[WRONG_VERSION],
        QuarantineReason.UNKNOWN_KIND: json.dumps(
            decoded | {"kind": "verdict"}
        ).encode(),
        QuarantineReason.INVALID_PROJECT_ID: json.dumps(
            decoded | {"project_id": ".."}
        ).encode(),
        QuarantineReason.INVALID_PAYLOAD: json.dumps(
            decoded | {"kind": SubmissionKind.RESOLUTION.value}
        ).encode(),
        QuarantineReason.NO_STORE_FOR_PROJECT: json.dumps(
            decoded | {"project_id": "never-created"}
        ).encode(),
    }


def test_every_quarantine_reason_lands_and_later_files_still_apply(
    supervisor_dir: Path,
    local_host: LocalHost,
    real_submission: RealSubmission,
    damaged_envelopes: dict[str, bytes],
) -> None:
    store = local_host.open_project(PROJECT)
    new = layout.new_dir(supervisor_dir)
    bad = _bad_files(real_submission, damaged_envelopes)
    # Prefixed to drain ahead of the one valid file, which is real_submission.
    for index, content in enumerate(bad.values()):
        (new / layout.submission_filename(index, f"bad-{index}")).write_bytes(content)

    InboxTenant(supervisor_dir).tick(local_host)

    entries = quarantined(supervisor_dir)
    assert {entry.reason for entry in entries} == set(QuarantineReason)
    assert all(entry.sidecar_error is None for entry in entries)
    assert pending(supervisor_dir) == []
    record = store.submission(FIXTURE_SUBMISSION_ID)
    assert record is not None and record.outcome is SubmissionOutcome.APPLIED


@pytest.mark.parametrize("unsafe_id", ["a/b", ".", ".."])
def test_a_hand_written_create_project_with_an_unsafe_id_creates_no_store(
    tmp_path: Path,
    supervisor_dir: Path,
    local_host: LocalHost,
    real_submission: RealSubmission,
    unsafe_id: str,
) -> None:
    """``submit()`` refuses these ids, so the file is written by hand."""
    envelope = json.loads(real_submission.content) | {
        "project_id": unsafe_id,
        "kind": SubmissionKind.CREATE_PROJECT,
        "payload": {},
    }
    name = layout.submission_filename(0, "unsafe")
    (layout.new_dir(supervisor_dir) / name).write_text(json.dumps(envelope))

    InboxTenant(supervisor_dir).tick(local_host)

    [entry] = [e for e in quarantined(supervisor_dir) if e.path.name == name]
    assert entry.reason is QuarantineReason.INVALID_PROJECT_ID
    assert list(tmp_path.rglob(f"*{STORE_FILE_SUFFIX}*")) == []


# --------------------------------------------------------------------------
# A sick store: the attempt counter and the failed/ park (F001)
# --------------------------------------------------------------------------

SICK_PROJECT = "sick"


def _make_sick(supervisor_dir: Path) -> Path:
    """A directory where the store file belongs: every open of it fails.

    Not discovered at start (it is not a file), so the process runs; every
    ``open_project`` for it raises ``StorePermissionError``.
    """
    sick = supervisor_dir / f"{SICK_PROJECT}{STORE_FILE_SUFFIX}"
    sick.mkdir(parents=True)
    return sick


def _submit_create(supervisor_dir: Path, project_id: str) -> str:
    return submit(
        project_id=project_id,
        kind=SubmissionKind.CREATE_PROJECT,
        payload={},
        submitted_by="tester",
        store_dir=supervisor_dir,
    )


def test_a_sick_store_is_counted_raised_then_parked_never_quarantined(
    supervisor_dir: Path, local_host: LocalHost, caplog: pytest.LogCaptureFixture
) -> None:
    _make_sick(supervisor_dir)
    local_host.settings = ProcessSettings(inbox_max_attempts=3)
    _submit_create(supervisor_dir, SICK_PROJECT)
    tenant = InboxTenant(supervisor_dir)

    # Below the limit: the failure stops the tick, and the count is on disk.
    for expected in (1, 2):
        with pytest.raises(StorePermissionError):
            tenant.tick(local_host)
        [entry] = pending(supervisor_dir)
        assert entry.attempts == expected

    # At the limit: parked, logged at ERROR, and the tick carries on.
    healthy_id = _submit_create(supervisor_dir, "healthy")
    with caplog.at_level(logging.ERROR, logger="amoeba.process.inbox_tenant"):
        assert tenant.tick(local_host) is True

    [parked] = failed(supervisor_dir)
    assert parked.attempts == 3
    assert parked.last_error is not None
    assert parked.last_error.startswith("StorePermissionError")
    assert parked.last_failed_at is not None
    assert "parked" in caplog.text
    assert quarantined(supervisor_dir) == []
    assert pending(supervisor_dir) == []
    record = local_host.store_for("healthy").submission(healthy_id)
    assert record is not None and record.outcome is SubmissionOutcome.APPLIED


def test_a_requeued_file_resumes_at_its_count_then_applies_once_fixed(
    supervisor_dir: Path, local_host: LocalHost
) -> None:
    sick = _make_sick(supervisor_dir)
    local_host.settings = ProcessSettings(inbox_max_attempts=2)
    submission_id = _submit_create(supervisor_dir, SICK_PROJECT)
    tenant = InboxTenant(supervisor_dir)
    with pytest.raises(StorePermissionError):
        tenant.tick(local_host)
    tenant.tick(local_host)
    [parked] = failed(supervisor_dir)
    assert parked.attempts == 2

    def requeue() -> Path:
        destination = layout.new_dir(supervisor_dir) / parked.path.name
        parked.path.replace(destination)
        layout.attempts_sidecar(parked.path).replace(
            layout.attempts_sidecar(destination)
        )
        return destination

    # Still sick. A fresh count (1, below the limit of 2) would raise; the
    # resumed count (3) parks again at once, without raising.
    requeue()
    assert tenant.tick(local_host) is True
    [reparked] = failed(supervisor_dir)
    assert reparked.attempts == 3

    # Fixed: it applies, and the file and its counter are both gone.
    sick.rmdir()
    requeued = requeue()
    assert tenant.tick(local_host) is True
    assert not requeued.exists()
    assert not layout.attempts_sidecar(requeued).exists()
    record = local_host.store_for(SICK_PROJECT).submission(submission_id)
    assert record is not None and record.outcome is SubmissionOutcome.APPLIED
