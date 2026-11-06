"""Rows for the inbox listings: ``inbox``, ``submissions``, and ``messages``.

The one ``LISTINGS`` registry registers these; nothing here is reachable
except through it.

``submissions`` and ``messages`` receive a **read-only** store. ``inbox`` reads
the supervisor directory (the project inbox and the program inbox under
``programs/``) and opens no store at all.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Final

from amoeba import inbox
from amoeba.inbox import layout
from amoeba.inspection.listing import ChoiceOption, ListingRequest, Row
from amoeba.store import Channel, Store
from amoeba.store.paths import program_dir

CHANNEL_OPTION = ChoiceOption(
    name="channel",
    help_text="Only this channel. Every channel when omitted.",
    choices=tuple(channel.value for channel in Channel),
)


def submission_rows(store: Store, request: ListingRequest) -> list[Row]:
    """Applied and rejected submissions for a project, in ``applied_seq`` order."""
    return [
        {
            "applied_seq": record.applied_seq,
            "id": record.id,
            "kind": record.kind.value,
            "outcome": record.outcome.value,
            "reason": record.reason or "",
            "submitted_by": record.submitted_by,
            "submitted_at": record.submitted_at.isoformat(),
            "payload": dict(record.payload),
        }
        for record in store.submissions(request.require_project_id())
    ]


def message_rows(store: Store, request: ListingRequest) -> list[Row]:
    """Messages for a project in ``seq`` order: one channel, or every one."""
    channel_value = request.option(CHANNEL_OPTION)
    channels = list(Channel) if channel_value is None else [Channel(channel_value)]
    messages = sorted(
        (
            message
            for channel in channels
            for message in store.messages(request.require_project_id(), channel=channel)
        ),
        key=lambda message: message.seq,
    )
    return [
        {
            "seq": message.seq,
            "id": message.id,
            "channel": message.channel.value,
            "node_id": message.node_id or "",
            "blocked_state_id": message.blocked_state_id or "",
            "journal_entry_id": message.journal_entry_id or "",
            "submission_id": message.submission_id or "",
            "acknowledged_at": (
                message.acknowledged_at.isoformat() if message.acknowledged_at else ""
            ),
            "acknowledgment_outcome": (
                message.acknowledgment_outcome.value
                if message.acknowledgment_outcome
                else ""
            ),
            "acknowledgment_reason": message.acknowledgment_reason or "",
            "fault_kind": message.fault_kind or "",
            "closed_at": message.closed_at.isoformat() if message.closed_at else "",
            "payload": dict(message.payload) if message.payload is not None else {},
        }
        for message in messages
    ]


#: The ``inbox`` listing's columns. ``queue`` is last, so the earlier columns keep
#: their names and positions for readers of project inbox rows.
INBOX_COLUMNS: Final = ("state", "file", "attempts", "reason", "problem", "queue")


class InboxQueue(StrEnum):
    """Which inbox root a file sits in: the project inbox or the program inbox."""

    PROJECT = "project"
    PROGRAM = "program"


def inbox_rows(supervisor_dir: Path) -> list[Row]:
    """Every file waiting in, or set aside by, either inbox. Opens no store.

    ``state`` is the directory the file sits in, named by ``layout``; ``queue``,
    the last column, is which inbox. The project inbox's rows come first and are
    exactly what they were before the program inbox existed, plus the key.
    """
    return [
        *_queue_rows(supervisor_dir, InboxQueue.PROJECT),
        *_queue_rows(program_dir(supervisor_dir), InboxQueue.PROGRAM),
    ]


def _queue_rows(root: Path, queue: InboxQueue) -> list[Row]:
    """The rows of one inbox, ``root`` being the directory that holds ``inbox/``."""
    return [
        *(
            {
                "state": layout.NEW_DIR_NAME,
                "file": entry.path.name,
                "attempts": "" if entry.attempts is None else entry.attempts,
                "reason": "",
                "problem": entry.sidecar_error or "",
                "queue": queue.value,
            }
            for entry in inbox.pending(root)
        ),
        *(
            {
                "state": layout.QUARANTINE_DIR_NAME,
                "file": entry.path.name,
                "attempts": "",
                "reason": entry.reason.value if entry.reason else "",
                "problem": entry.sidecar_error or entry.detail or "",
                "queue": queue.value,
            }
            for entry in inbox.quarantined(root)
        ),
        *(
            {
                "state": layout.FAILED_DIR_NAME,
                "file": entry.path.name,
                "attempts": "" if entry.attempts is None else entry.attempts,
                "reason": "",
                "problem": entry.sidecar_error or entry.last_error or "",
                "queue": queue.value,
            }
            for entry in inbox.failed(root)
        ),
    ]
