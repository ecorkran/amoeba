"""``InboxDrain`` — the file lifecycle every inbox tenant shares.

An inbox root holds ``tmp/``, ``new/``, ``quarantine/`` and ``failed/`` (see
``amoeba.inbox.layout``). The drain walks ``new/`` in order and ends each file
in exactly one terminal place:

- **applied or rejected** — a store record; the file and any counter deleted;
- **quarantined** — it cannot be parsed or attributed: moved to ``quarantine/``
  with a ``.reason.json``;
- **failed** — valid, but its apply raised ``inbox_max_attempts`` times: moved
  to ``failed/`` with its counter.

**Order is the crash-safety argument.** The file is deleted only *after* the
apply commits: a crash in between leaves a recorded submission and a file that
replays as a no-op. The counter goes before the file for the same reason — a
crash between them leaves no orphan counter behind.

**A sick store is not a bad submission.** An exception from the apply is never
turned into a quarantine. Below the attempt limit it is logged and re-raised, so
the process stops and the operator hears about it; at the limit the file is
parked and the queue moves on, so a store restarting cannot fix does not hold
the process down forever.

What differs between inboxes is injected: the root, how a file is parsed, how a
parsed envelope is screened (attribution), and how it is applied. The tenants
own those; nothing here knows a project or a program.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from amoeba.inbox import layout
from amoeba.inbox.durable import fsync_directory, write_durably
from amoeba.inbox.envelope import EnvelopeError
from amoeba.inbox.sidecars import (
    AttemptsSidecar,
    ReasonSidecar,
    SidecarError,
    read_sidecar,
)
from amoeba.process.settings import ProcessSettings
from amoeba.store import QuarantineReason

logger = logging.getLogger(__name__)


class DrainHost(Protocol):
    """What the drain needs from its host — ``ResidentProcess`` provides it."""

    @property
    def settings(self) -> ProcessSettings: ...

    @property
    def stop_requested(self) -> bool: ...


class DrainedEnvelope(Protocol):
    """The parsed envelope members the reused-id check reads."""

    @property
    def id(self) -> str: ...

    @property
    def kind(self) -> object: ...

    @property
    def submitted_by(self) -> str: ...

    @property
    def payload(self) -> Mapping[str, object]: ...


class DrainedRecord(Protocol):
    """The store record members the reused-id check reads."""

    @property
    def kind(self) -> object: ...

    @property
    def submitted_by(self) -> str: ...

    @property
    def payload(self) -> Mapping[str, object]: ...


class InboxDrain[
    HostT: DrainHost,
    EnvelopeT: DrainedEnvelope,
    RecordT: DrainedRecord,
]:
    """Drains one inbox root, at most ``inbox_batch_size`` files per tick."""

    def __init__(
        self,
        root: Path,
        *,
        parse: Callable[[bytes], EnvelopeT],
        screen: Callable[[HostT, EnvelopeT], tuple[QuarantineReason, str] | None],
        apply: Callable[[HostT, EnvelopeT], RecordT],
    ) -> None:
        """Build a drain over ``root``'s inbox.

        Args:
            root: The directory holding ``inbox/`` (the layout functions' root).
            parse: Parses a file's bytes; raises ``EnvelopeError`` for a bad one.
            screen: Returns a quarantine reason and detail for an envelope that
                cannot be attributed, or ``None``. Never touches a store.
            apply: Applies an envelope and returns its record. Any exception is
                counted as a sick store, never a bad submission.
        """
        self._root = root
        self._parse = parse
        self._screen = screen
        self._apply = apply

    def tick(self, host: HostT) -> bool:
        """Handle up to ``inbox_batch_size`` files in drain order.

        Checks ``stop_requested`` between files; each file is one short
        transaction, so an abandoned tick is covered by the crash table.

        Returns:
            Whether any file was handled.

        Raises:
            Exception: Whatever ``apply`` raised, while the file's attempt count
                is below the limit.
        """
        batch = layout.submission_files(layout.new_dir(self._root))
        handled = False
        for path in batch[: host.settings.inbox_batch_size]:
            if host.stop_requested:
                break
            self._handle(host, path)
            handled = True
        return handled

    # ----------------------------------------------------------------------
    # One file
    # ----------------------------------------------------------------------

    def _handle(self, host: HostT, path: Path) -> None:
        try:
            envelope = self._parse(path.read_bytes())
        except EnvelopeError as error:
            # Specific: a bad submission, not a sick store — quarantine it and
            # let later files in this tick still apply.
            self._quarantine(path, error.reason, error.detail)
            return

        if (unattributed := self._screen(host, envelope)) is not None:
            self._quarantine(path, *unattributed)
            return

        try:
            record = self._apply(host, envelope)
        except Exception as error:
            # Any failure here means the store is unwell, not the submission.
            # Counted on disk; parked at the limit, re-raised below it.
            counter = self._count_failure(host, path, error)
            limit = host.settings.inbox_max_attempts
            if counter.attempts >= limit:
                logger.exception(
                    "apply of %s failed %d times; parked in %s, continuing",
                    path.name,
                    counter.attempts,
                    layout.FAILED_DIR_NAME,
                )
                return
            logger.exception(
                "apply of %s failed (attempt %d of %d); stopping",
                path.name,
                counter.attempts,
                limit,
            )
            raise

        _warn_on_reused_id(record, envelope)
        layout.attempts_sidecar(path).unlink(missing_ok=True)
        path.unlink()

    # ----------------------------------------------------------------------
    # Quarantine: this submission is bad
    # ----------------------------------------------------------------------

    def _quarantine(self, path: Path, reason: QuarantineReason, detail: str) -> None:
        """Move a file to ``quarantine/`` behind its reason. Never deletes."""
        destination = layout.quarantine_dir(self._root) / path.name
        destination.parent.mkdir(parents=True, exist_ok=True)
        sidecar = ReasonSidecar(
            reason=reason, detail=detail, quarantined_at=datetime.now(UTC)
        )
        # The sidecar first, so the listing never sees a reasonless file.
        self._write_sidecar(
            sidecar.model_dump_json(), layout.reason_sidecar(destination)
        )
        self._move(path, destination)
        # A requeued file may carry a counter; it travels with the file.
        if (counter := layout.attempts_sidecar(path)).exists():
            self._move(counter, layout.attempts_sidecar(destination))
        logger.warning("quarantined %s: %s (%s)", path.name, reason.value, detail)

    # ----------------------------------------------------------------------
    # Attempts: the store is unwell
    # ----------------------------------------------------------------------

    def _count_failure(
        self, host: HostT, path: Path, error: Exception
    ) -> AttemptsSidecar:
        """Record one failed apply on disk; park the file if it hit the limit.

        Below the limit the counter is written beside the file in ``new/``; at
        it, file and counter move to ``failed/``. The caller logs and decides
        whether to re-raise.
        """
        counter = AttemptsSidecar(
            attempts=self._previous_attempts(path) + 1,
            last_error=f"{type(error).__name__}: {error}",
            last_failed_at=datetime.now(UTC),
        )
        if counter.attempts >= host.settings.inbox_max_attempts:
            self._park(path, counter)
        else:
            self._write_sidecar(
                counter.model_dump_json(), layout.attempts_sidecar(path)
            )
        return counter

    def _previous_attempts(self, path: Path) -> int:
        """The recorded count: zero when absent, including after a requeue."""
        counter = layout.attempts_sidecar(path)
        if not counter.exists():
            return 0
        try:
            return read_sidecar(counter, AttemptsSidecar).attempts
        except SidecarError:
            # Specific: an unreadable counter. Counted from zero, loudly, and
            # overwritten with a valid one — raising here instead would bring
            # back the unbounded crash loop the counter exists to end.
            logger.warning(
                "unreadable attempt counter for %s; restarting it", path.name
            )
            return 0

    def _park(self, path: Path, counter: AttemptsSidecar) -> None:
        """Move a file and its counter to ``failed/``. Never deletes content."""
        destination = layout.failed_dir(self._root) / path.name
        destination.parent.mkdir(parents=True, exist_ok=True)
        self._write_sidecar(
            counter.model_dump_json(), layout.attempts_sidecar(destination)
        )
        self._move(path, destination)
        layout.attempts_sidecar(path).unlink(missing_ok=True)

    # ----------------------------------------------------------------------
    # Durable file operations
    # ----------------------------------------------------------------------

    def _write_sidecar(self, content: str, final_path: Path) -> None:
        """The same tmp-and-rename ``submit()`` uses."""
        tmp = layout.tmp_dir(self._root)
        tmp.mkdir(parents=True, exist_ok=True)
        write_durably(content, tmp_path=tmp / final_path.name, final_path=final_path)

    @staticmethod
    def _move(path: Path, destination: Path) -> None:
        path.replace(destination)
        fsync_directory(destination.parent)
        fsync_directory(path.parent)


def _warn_on_reused_id(record: DrainedRecord, envelope: DrainedEnvelope) -> None:
    """D2: a reused id with different content is a no-op, first one wins.

    Logged, not raised: the second file may be a legitimate retry. Only the
    timestamp may differ between a retry and its original.
    """
    if (record.kind, record.submitted_by, dict(record.payload)) != (
        envelope.kind,
        envelope.submitted_by,
        dict(envelope.payload),
    ):
        logger.warning(
            "submission id %s reused with different content; the first applied "
            "submission stands",
            envelope.id,
        )
