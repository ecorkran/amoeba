"""Read-only listings of what sits in the inbox: pending, quarantined, failed.

They open no store and work whether or not the process is running. A stray
file in ``tmp/`` appears in none of them — it is harmless and a submitter that
saw no success retries. A missing or damaged sidecar is reported on the entry,
never allowed to crash the listing and never replaced by a made-up value.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from amoeba.inbox import layout
from amoeba.inbox.sidecars import (
    AttemptsSidecar,
    ReasonSidecar,
    SidecarError,
    read_sidecar,
)
from amoeba.store import paths
from amoeba.store.inbox_models import QuarantineReason


@dataclass(frozen=True)
class PendingSubmission:
    """A file in ``new/``, awaiting apply.

    ``attempts`` counts earlier failed applies: ``0`` when none is recorded,
    ``None`` when a counter exists but cannot be read (see ``sidecar_error``).
    """

    path: Path
    attempts: int | None
    sidecar_error: str | None = None


@dataclass(frozen=True)
class QuarantinedSubmission:
    """A file that could not be attributed, with the recorded reason."""

    path: Path
    reason: QuarantineReason | None
    detail: str | None
    sidecar_error: str | None = None


@dataclass(frozen=True)
class FailedSubmission:
    """A valid file whose apply failed ``inbox_max_attempts`` times."""

    path: Path
    attempts: int | None
    last_error: str | None
    last_failed_at: datetime | None
    sidecar_error: str | None = None


def _resolve(store_dir: Path | None) -> Path:
    return paths.store_dir() if store_dir is None else store_dir


def _pending_entry(path: Path) -> PendingSubmission:
    counter = layout.attempts_sidecar(path)
    if not counter.exists():
        return PendingSubmission(path=path, attempts=0)
    try:
        return PendingSubmission(
            path=path, attempts=read_sidecar(counter, AttemptsSidecar).attempts
        )
    except SidecarError as error:
        # Specific: reported on the entry so one bad counter cannot hide the rest.
        return PendingSubmission(path=path, attempts=None, sidecar_error=str(error))


def _quarantined_entry(path: Path) -> QuarantinedSubmission:
    try:
        sidecar = read_sidecar(layout.reason_sidecar(path), ReasonSidecar)
    except SidecarError as error:
        # Specific: reported on the entry so one bad sidecar cannot hide the rest.
        return QuarantinedSubmission(
            path=path, reason=None, detail=None, sidecar_error=str(error)
        )
    return QuarantinedSubmission(
        path=path, reason=sidecar.reason, detail=sidecar.detail
    )


def _failed_entry(path: Path) -> FailedSubmission:
    try:
        sidecar = read_sidecar(layout.attempts_sidecar(path), AttemptsSidecar)
    except SidecarError as error:
        # Specific: reported on the entry so one bad sidecar cannot hide the rest.
        return FailedSubmission(
            path=path,
            attempts=None,
            last_error=None,
            last_failed_at=None,
            sidecar_error=str(error),
        )
    return FailedSubmission(
        path=path,
        attempts=sidecar.attempts,
        last_error=sidecar.last_error,
        last_failed_at=sidecar.last_failed_at,
    )


def pending(store_dir: Path | None = None) -> list[PendingSubmission]:
    """Files in ``new/``, in drain order — which is **not** authoritative order."""
    directory = layout.new_dir(_resolve(store_dir))
    return [_pending_entry(path) for path in layout.submission_files(directory)]


def quarantined(store_dir: Path | None = None) -> list[QuarantinedSubmission]:
    """Quarantined files, each with the reason from its ``.reason.json``."""
    directory = layout.quarantine_dir(_resolve(store_dir))
    return [_quarantined_entry(path) for path in layout.submission_files(directory)]


def failed(store_dir: Path | None = None) -> list[FailedSubmission]:
    """Parked files, each with its attempt count and last error."""
    directory = layout.failed_dir(_resolve(store_dir))
    return [_failed_entry(path) for path in layout.submission_files(directory)]
