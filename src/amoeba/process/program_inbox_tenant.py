"""``ProgramInboxTenant`` — drains ``programs/inbox/new/`` into the program store.

The second inbox tenant. The file lifecycle (terminal places, crash-safety
order, quarantine, attempt counting) is ``InboxDrain``'s, shared with the project
inbox; what is specific here is parsing a program envelope and applying it with
``ProgramStore.apply_submission``. A program submission is attributed to no
project, so there is nothing to screen: every parsed envelope is applied.

The program store does not exist until the first submission. The apply creates
it atomically through the host (``ensure_program_store``), so a store that cannot
be created or written is a sick store, counted and stopped on like a project's.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from amoeba.inbox.program_envelope import (
    ProgramSubmissionEnvelope,
    parse_program_envelope,
)
from amoeba.process.inbox_drain import DrainHost, InboxDrain
from amoeba.store import ProgramStore, ProgramSubmissionRecord
from amoeba.store.paths import program_dir

#: How this tenant appears in logs, including a grace-expiry ERROR.
PROGRAM_INBOX_TENANT_NAME = "program-inbox"


class ProgramInboxHost(DrainHost, Protocol):
    """What the tenant needs from its host — ``ResidentProcess`` provides it."""

    def ensure_program_store(self) -> ProgramStore: ...


class ProgramInboxTenant:
    """Applies program submissions, at most ``inbox_batch_size`` per tick."""

    def __init__(self, supervisor_dir: Path) -> None:
        """Build a tenant draining ``supervisor_dir``'s program inbox."""
        self._drain: InboxDrain[
            ProgramInboxHost, ProgramSubmissionEnvelope, ProgramSubmissionRecord
        ] = InboxDrain(
            program_dir(supervisor_dir),
            parse=parse_program_envelope,
            apply=_apply,
        )

    @property
    def name(self) -> str:
        return PROGRAM_INBOX_TENANT_NAME

    def tick(self, host: ProgramInboxHost) -> bool:
        """Handle up to ``inbox_batch_size`` files in drain order.

        Returns:
            Whether any file was handled.

        Raises:
            Exception: Whatever creating the store or ``apply_submission``
                raised, while the file's attempt count is below the limit.
        """
        return self._drain.tick(host)


def _apply(
    host: ProgramInboxHost, envelope: ProgramSubmissionEnvelope
) -> ProgramSubmissionRecord:
    return host.ensure_program_store().apply_submission(
        submission_id=envelope.id,
        kind=envelope.kind,
        submitted_by=envelope.submitted_by,
        submitted_at=envelope.submitted_at,
        payload=envelope.payload,
    )
