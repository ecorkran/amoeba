"""``InboxTenant`` — drains ``inbox/new/`` into the project stores.

The first real tenant, and the module that knows both ``amoeba.inbox`` and the
project store's write path. The file lifecycle — terminal places, crash-safety
order, and the rule that a sick store is never a bad submission — lives in
``process/inbox_drain.py`` and is shared with the program inbox. What stays here
is what is specific to project submissions: parsing a project envelope,
attributing it to an open store (``no_store_for_project``), and applying it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from amoeba.inbox.envelope import SubmissionEnvelope, parse_envelope
from amoeba.process.inbox_drain import DrainHost, InboxDrain
from amoeba.store import (
    QuarantineReason,
    Store,
    SubmissionKind,
    SubmissionRecord,
)

#: How this tenant appears in logs, including a grace-expiry ERROR.
INBOX_TENANT_NAME = "inbox"


class InboxHost(DrainHost, Protocol):
    """What the tenant needs from its host — ``ResidentProcess`` provides it.

    Declared as a protocol so the tenant depends on exactly these members and
    nothing else the host happens to have.
    """

    @property
    def project_ids(self) -> tuple[str, ...]: ...

    def store_for(self, project_id: str) -> Store: ...

    def open_project(self, project_id: str) -> Store: ...


class InboxTenant:
    """Applies inbox submissions, at most ``inbox_batch_size`` per tick."""

    def __init__(self, supervisor_dir: Path) -> None:
        """Build a tenant draining ``supervisor_dir``'s inbox."""
        self._drain: InboxDrain[InboxHost, SubmissionEnvelope, SubmissionRecord] = (
            InboxDrain(
                supervisor_dir,
                parse=parse_envelope,
                screen=_screen,
                apply=_apply,
            )
        )

    @property
    def name(self) -> str:
        return INBOX_TENANT_NAME

    def tick(self, host: InboxHost) -> bool:
        """Handle up to ``inbox_batch_size`` files in drain order.

        Returns:
            Whether any file was handled.

        Raises:
            Exception: Whatever ``open_project`` or ``apply_submission``
                raised, while the file's attempt count is below the limit.
        """
        return self._drain.tick(host)


def _screen(
    host: InboxHost, envelope: SubmissionEnvelope
) -> tuple[QuarantineReason, str] | None:
    """A project submission needs an open store, unless it creates the project."""
    if (
        envelope.kind is not SubmissionKind.CREATE_PROJECT
        and envelope.project_id not in host.project_ids
    ):
        # Raced ahead of, or was never preceded by, its project's creation.
        return (
            QuarantineReason.NO_STORE_FOR_PROJECT,
            f"no open store for project {envelope.project_id!r}",
        )
    return None


def _apply(host: InboxHost, envelope: SubmissionEnvelope) -> SubmissionRecord:
    if envelope.kind is SubmissionKind.CREATE_PROJECT:
        store = host.open_project(envelope.project_id)
    else:
        store = host.store_for(envelope.project_id)
    return store.apply_submission(
        submission_id=envelope.id,
        project_id=envelope.project_id,
        kind=envelope.kind,
        submitted_by=envelope.submitted_by,
        submitted_at=envelope.submitted_at,
        payload=envelope.payload,
    )
