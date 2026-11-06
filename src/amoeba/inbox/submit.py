"""``submit()`` — the only write path open to parts outside the process.

It opens no store. It validates, writes one file durably into ``inbox/new/``,
and returns the submission id. It works whether or not the resident process is
running; the process drains the file when it next ticks.

A submitter learns the outcome by reading, not by reply:
``Store.open_read_only(project_id=…).submission(submission_id)`` is ``None``
until the submission is applied.
"""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path

from amoeba.inbox import layout
from amoeba.inbox.durable import write_durably
from amoeba.inbox.envelope import EnvelopeError, build_envelope
from amoeba.inbox.program_envelope import build_program_envelope
from amoeba.store import paths
from amoeba.store.inbox_models import QuarantineReason, SubmissionKind
from amoeba.store.program_models import ProgramSubmissionKind

logger = logging.getLogger(__name__)

_NANOSECONDS_PER_SECOND = 1_000_000_000


class InboxSubmitError(Exception):
    """Base class for every error ``submit()`` raises. Nothing was submitted."""


class InvalidSubmissionError(InboxSubmitError):
    """The submission failed validation. Carries the reason a drained file
    with the same content would have been quarantined for."""

    def __init__(self, reason: QuarantineReason, detail: str) -> None:
        super().__init__(f"{reason.value}: {detail}")
        self.reason = reason
        self.detail = detail


class SubmissionWriteError(InboxSubmitError):
    """The submission was valid but could not be written durably."""


def submit(
    *,
    project_id: str,
    kind: SubmissionKind,
    payload: Mapping[str, object],
    submitted_by: str,
    submission_id: str | None = None,
    store_dir: Path | None = None,
) -> str:
    """Submit one change for the resident process to apply.

    Args:
        project_id: The project it is for.
        kind: What it asks for.
        payload: The kind's fields.
        submitted_by: Free-form provenance.
        submission_id: The idempotency key. Pass the same id back to retry
            safely (D2); one is generated when omitted.
        store_dir: The supervisor directory. Resolved from the environment when
            omitted, exactly as the store path is.

    Returns:
        The submission id, once the file is fsync-durable in ``inbox/new/``.

    Raises:
        InvalidSubmissionError: If the project id, envelope, or payload is
            invalid. Checked before anything is written.
        SubmissionWriteError: If the file could not be written. Nothing is
            left in ``new/`` or ``tmp/``.
    """
    identifier = uuid.uuid4().hex if submission_id is None else submission_id
    submitted_at_ns = time.time_ns()
    submitted_at = _instant(submitted_at_ns)

    try:
        envelope = build_envelope(
            submission_id=identifier,
            project_id=project_id,
            kind=kind,
            submitted_by=submitted_by,
            submitted_at=submitted_at,
            payload=payload,
        )
    except EnvelopeError as error:
        raise InvalidSubmissionError(error.reason, error.detail) from error

    directory = paths.store_dir() if store_dir is None else store_dir
    _write_submission(
        directory, identifier, submitted_at_ns, envelope.model_dump_json()
    )
    return identifier


def submit_program(
    *,
    kind: ProgramSubmissionKind,
    payload: Mapping[str, object],
    submitted_by: str,
    submission_id: str | None = None,
    store_dir: Path | None = None,
) -> str:
    """Submit one program change for the resident process to apply.

    The same durability and idempotency as :func:`submit`, into the program
    inbox (``programs/inbox/new/``). A program submission is attributed to no
    project, so there is no project id.

    Args:
        kind: What it asks for.
        payload: The kind's fields.
        submitted_by: Free-form provenance.
        submission_id: The idempotency key; one is generated when omitted.
        store_dir: The supervisor directory, resolved as for :func:`submit`.

    Returns:
        The submission id, once the file is fsync-durable.

    Raises:
        InvalidSubmissionError: If the envelope or payload is invalid. Checked
            before anything is written.
        SubmissionWriteError: If the file could not be written.
    """
    identifier = uuid.uuid4().hex if submission_id is None else submission_id
    submitted_at_ns = time.time_ns()

    try:
        envelope = build_program_envelope(
            submission_id=identifier,
            kind=kind,
            submitted_by=submitted_by,
            submitted_at=_instant(submitted_at_ns),
            payload=payload,
        )
    except EnvelopeError as error:
        raise InvalidSubmissionError(error.reason, error.detail) from error

    directory = paths.store_dir() if store_dir is None else store_dir
    _write_submission(
        paths.program_dir(directory),
        identifier,
        submitted_at_ns,
        envelope.model_dump_json(),
    )
    return identifier


def _instant(submitted_at_ns: int) -> datetime:
    return datetime.fromtimestamp(submitted_at_ns / _NANOSECONDS_PER_SECOND, tz=UTC)


def _write_submission(
    root: Path, identifier: str, submitted_at_ns: int, content: str
) -> None:
    """Write one envelope durably into ``root``'s inbox ``new/``.

    ``root`` is the directory holding ``inbox/``: the supervisor directory for a
    project submission, ``programs/`` for a program submission.
    """
    name = layout.submission_filename(submitted_at_ns, identifier)
    try:
        layout.tmp_dir(root).mkdir(parents=True, exist_ok=True)
        layout.new_dir(root).mkdir(parents=True, exist_ok=True)
        write_durably(
            content,
            tmp_path=layout.tmp_dir(root) / name,
            final_path=layout.new_dir(root) / name,
        )
    except OSError as error:
        logger.exception("cannot write submission %s", identifier)
        raise SubmissionWriteError(
            f"cannot write submission {identifier!r}: {error}"
        ) from error
