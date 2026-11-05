"""ProgramInboxTenant: the apply loop, quarantine, and the attempt counter.

Driven in-process through ``LocalHost`` — a real program store, real files, the
real tick — mirroring ``test_inbox_tenant.py``. The listings take the directory
that holds ``inbox/``, so passing ``programs/`` lists the program inbox.
"""

from __future__ import annotations

import json
import logging
import textwrap
from pathlib import Path

import pytest
from host_harness import FAILED_MARKER, TenantSpec, start_host
from local_host_harness import LocalHost
from program_harness import member, member_payload, program_payload

from amoeba.inbox import failed, layout, pending, quarantined, submit, submit_program
from amoeba.inbox.sidecars import ReasonSidecar, read_sidecar
from amoeba.process.inbox_tenant import InboxTenant
from amoeba.process.program_inbox_tenant import ProgramInboxTenant
from amoeba.process.settings import ProcessSettings
from amoeba.store import (
    ProgramSubmissionKind,
    QuarantineReason,
    StoreCorruptError,
    SubmissionKind,
    SubmissionOutcome,
)
from amoeba.store.inbox_models import INTENT_BODY
from amoeba.store.paths import program_dir, program_store_path

STORE_FAILURE_TYPE = StoreCorruptError


def _submit_program(
    supervisor_dir: Path,
    payload: dict[str, object] | None = None,
    *,
    kind: ProgramSubmissionKind = ProgramSubmissionKind.REGISTER_PROGRAM,
    submission_id: str | None = None,
) -> str:
    return submit_program(
        kind=kind,
        payload=payload if payload is not None else program_payload(),
        submitted_by="tester",
        submission_id=submission_id,
        store_dir=supervisor_dir,
    )


def _program_inbox(supervisor_dir: Path) -> Path:
    return program_dir(supervisor_dir)


def _make_program_store_sick(supervisor_dir: Path) -> None:
    """Junk where the store belongs: every open of it raises ``StoreCorruptError``."""
    path = program_store_path(supervisor_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"junk, not a database" * 20)


def test_a_valid_file_applies_creates_the_store_and_is_deleted(
    supervisor_dir: Path, local_host: LocalHost
) -> None:
    assert not program_store_path(supervisor_dir).exists()
    submission_id = _submit_program(supervisor_dir)

    assert ProgramInboxTenant(supervisor_dir).tick(local_host) is True

    assert program_store_path(supervisor_dir).is_file()
    store = local_host.program_store
    assert store is not None
    record = store.submission(submission_id)
    assert record is not None and record.outcome is SubmissionOutcome.APPLIED
    assert [p.program_id for p in store.programs()] == ["demo"]
    assert pending(_program_inbox(supervisor_dir)) == []


def test_a_rejection_is_recorded_and_the_file_is_deleted(
    supervisor_dir: Path, local_host: LocalHost
) -> None:
    submission_id = _submit_program(
        supervisor_dir,
        member_payload(member("ui"), program_id="nope"),
        kind=ProgramSubmissionKind.REGISTER_MEMBER,
    )

    ProgramInboxTenant(supervisor_dir).tick(local_host)

    store = local_host.program_store
    assert store is not None
    record = store.submission(submission_id)
    assert record is not None
    assert record.outcome is SubmissionOutcome.REJECTED
    assert str(record.reason).startswith("unknown_program: ")
    assert pending(_program_inbox(supervisor_dir)) == []


def test_an_empty_inbox_reports_no_work_and_creates_no_store(
    supervisor_dir: Path, local_host: LocalHost
) -> None:
    assert ProgramInboxTenant(supervisor_dir).tick(local_host) is False
    assert not program_store_path(supervisor_dir).exists()


def test_a_tick_handles_at_most_the_batch_size(
    supervisor_dir: Path, local_host: LocalHost
) -> None:
    local_host.settings = ProcessSettings(inbox_batch_size=2)
    for index in range(5):
        _submit_program(
            supervisor_dir,
            member_payload(member(f"m{index}"), program_id="nope"),
            kind=ProgramSubmissionKind.REGISTER_MEMBER,
        )

    ProgramInboxTenant(supervisor_dir).tick(local_host)

    assert len(pending(_program_inbox(supervisor_dir))) == 3


# --------------------------------------------------------------------------
# The four quarantine reasons
# --------------------------------------------------------------------------


def _bad_files(good: bytes) -> dict[QuarantineReason, bytes]:
    """One file per applicable reason, derived from real ``submit_program`` bytes."""
    decoded = json.loads(good)
    bad_payload = json.loads(good)
    del bad_payload["payload"]["concept_path"]
    return {
        QuarantineReason.UNPARSEABLE_ENVELOPE: good[: len(good) // 2],
        QuarantineReason.UNKNOWN_ENVELOPE_VERSION: json.dumps(
            decoded | {"envelope_version": 99}
        ).encode(),
        QuarantineReason.UNKNOWN_KIND: json.dumps(
            decoded | {"kind": "remove_member"}
        ).encode(),
        QuarantineReason.INVALID_PAYLOAD: json.dumps(bad_payload).encode(),
    }


def test_each_quarantine_reason_lands_with_its_sidecar_and_later_files_apply(
    supervisor_dir: Path, local_host: LocalHost
) -> None:
    _submit_program(supervisor_dir, submission_id="good")
    new = layout.new_dir(_program_inbox(supervisor_dir))
    [good_path] = layout.submission_files(new)
    good = good_path.read_bytes()
    # Prefixed to drain ahead of the one valid file.
    for index, content in enumerate(_bad_files(good).values()):
        (new / layout.submission_filename(index, f"bad-{index}")).write_bytes(content)

    ProgramInboxTenant(supervisor_dir).tick(local_host)

    entries = quarantined(_program_inbox(supervisor_dir))
    assert {entry.reason for entry in entries} == set(_bad_files(good))
    assert all(entry.sidecar_error is None for entry in entries)
    assert pending(_program_inbox(supervisor_dir)) == []
    store = local_host.program_store
    assert store is not None
    record = store.submission("good")
    assert record is not None and record.outcome is SubmissionOutcome.APPLIED


def test_an_invalid_payload_sidecar_names_the_offending_field(
    supervisor_dir: Path, local_host: LocalHost
) -> None:
    _submit_program(supervisor_dir)
    [path] = layout.submission_files(layout.new_dir(_program_inbox(supervisor_dir)))
    data = json.loads(path.read_bytes())
    del data["payload"]["concept_member"]
    path.write_text(json.dumps(data))

    ProgramInboxTenant(supervisor_dir).tick(local_host)

    [entry] = quarantined(_program_inbox(supervisor_dir))
    assert entry.reason is QuarantineReason.INVALID_PAYLOAD
    sidecar = read_sidecar(layout.reason_sidecar(entry.path), ReasonSidecar)
    assert "concept_member" in sidecar.detail


# --------------------------------------------------------------------------
# A sick store: counted, raised below the limit, parked at it
# --------------------------------------------------------------------------


def test_a_store_failure_below_the_limit_reraises_with_a_counter_beside_the_file(
    supervisor_dir: Path, local_host: LocalHost
) -> None:
    local_host.settings = ProcessSettings(inbox_max_attempts=3)
    _make_program_store_sick(supervisor_dir)
    _submit_program(supervisor_dir)
    tenant = ProgramInboxTenant(supervisor_dir)

    for expected in (1, 2):
        with pytest.raises(STORE_FAILURE_TYPE):
            tenant.tick(local_host)
        [entry] = pending(_program_inbox(supervisor_dir))
        assert entry.attempts == expected


def test_at_the_limit_the_file_is_parked_in_failed_and_the_tick_continues(
    supervisor_dir: Path,
    local_host: LocalHost,
    caplog: pytest.LogCaptureFixture,
) -> None:
    local_host.settings = ProcessSettings(inbox_max_attempts=2)
    _make_program_store_sick(supervisor_dir)
    _submit_program(supervisor_dir)
    tenant = ProgramInboxTenant(supervisor_dir)
    with pytest.raises(STORE_FAILURE_TYPE):
        tenant.tick(local_host)

    with caplog.at_level(logging.ERROR):
        assert tenant.tick(local_host) is True

    [parked] = failed(_program_inbox(supervisor_dir))
    assert parked.attempts == 2
    assert parked.last_error is not None
    assert parked.last_error.startswith("StoreCorruptError")
    assert "parked" in caplog.text
    assert quarantined(_program_inbox(supervisor_dir)) == []
    assert pending(_program_inbox(supervisor_dir)) == []


def test_the_resident_process_exits_as_a_store_failure(
    tmp_path: Path, supervisor_dir: Path
) -> None:
    """A failing program store apply stops a real process, as a project's does."""
    tenant = TenantSpec(
        body=textwrap.dedent(
            f"""
            from pathlib import Path
            from amoeba.process.program_inbox_tenant import ProgramInboxTenant

            if not hasattr(self, "inner"):
                self.inner = ProgramInboxTenant(Path({str(supervisor_dir)!r}))
            return self.inner.tick(host)
            """
        ).strip(),
        name="program-inbox",
    )
    process = start_host(tmp_path, supervisor_dir, tenant=tenant)
    try:
        process.await_ready()
        _make_program_store_sick(supervisor_dir)
        _submit_program(supervisor_dir)

        assert process.wait() != 0
        assert f"{FAILED_MARKER} {STORE_FAILURE_TYPE.__name__}" in "\n".join(
            process.remaining_stdout()
        )
    finally:
        process.cleanup()


# --------------------------------------------------------------------------
# First wins, and the two inboxes stay apart
# --------------------------------------------------------------------------


def test_a_reused_id_with_different_content_keeps_the_first_and_warns(
    supervisor_dir: Path,
    local_host: LocalHost,
    caplog: pytest.LogCaptureFixture,
) -> None:
    tenant = ProgramInboxTenant(supervisor_dir)
    _submit_program(supervisor_dir, submission_id="same")
    tenant.tick(local_host)
    _submit_program(
        supervisor_dir, program_payload(program_id="other"), submission_id="same"
    )

    with caplog.at_level(logging.WARNING):
        tenant.tick(local_host)

    store = local_host.program_store
    assert store is not None
    assert [p.program_id for p in store.programs()] == ["demo"]
    assert len(store.submissions()) == 1
    assert [
        record.levelno
        for record in caplog.records
        if "reused with different content" in record.getMessage()
    ] == [logging.WARNING]
    assert pending(_program_inbox(supervisor_dir)) == []


def test_each_tenant_leaves_the_other_inboxs_files_alone(
    supervisor_dir: Path, local_host: LocalHost
) -> None:
    local_host.open_project("demo")
    _submit_program(supervisor_dir)
    project_id = submit(
        project_id="demo",
        kind=SubmissionKind.INTENT,
        payload={INTENT_BODY: {"want": "x"}},
        submitted_by="tester",
        store_dir=supervisor_dir,
    )

    ProgramInboxTenant(supervisor_dir).tick(local_host)
    assert len(pending(supervisor_dir)) == 1
    assert pending(_program_inbox(supervisor_dir)) == []

    _submit_program(supervisor_dir, submission_id="second")
    InboxTenant(supervisor_dir).tick(local_host)
    assert pending(supervisor_dir) == []
    assert len(pending(_program_inbox(supervisor_dir))) == 1
    assert local_host.store_for("demo").submission(project_id) is not None
