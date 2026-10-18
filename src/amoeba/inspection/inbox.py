"""Rows for the inbox listings: ``inbox``, ``submissions``, and ``messages``.

The one ``LISTINGS`` registry registers these; nothing here is reachable
except through it.

``submissions`` and ``messages`` receive a **read-only** store. ``inbox`` reads
the supervisor directory and opens no store at all.
"""

from __future__ import annotations

from pathlib import Path

from amoeba import inbox
from amoeba.inbox import layout
from amoeba.inspection.listing import ChoiceOption, ListingRequest, Row
from amoeba.store import Channel, Store

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
            "payload": dict(message.payload) if message.payload is not None else {},
        }
        for message in messages
    ]


def inbox_rows(supervisor_dir: Path) -> list[Row]:
    """Every file waiting in, or set aside by, the inbox. Opens no store.

    ``state`` is the directory the file sits in, named by ``layout``.
    """
    return [
        *(
            {
                "state": layout.NEW_DIR_NAME,
                "file": entry.path.name,
                "attempts": "" if entry.attempts is None else entry.attempts,
                "reason": "",
                "problem": entry.sidecar_error or "",
            }
            for entry in inbox.pending(supervisor_dir)
        ),
        *(
            {
                "state": layout.QUARANTINE_DIR_NAME,
                "file": entry.path.name,
                "attempts": "",
                "reason": entry.reason.value if entry.reason else "",
                "problem": entry.sidecar_error or entry.detail or "",
            }
            for entry in inbox.quarantined(supervisor_dir)
        ),
        *(
            {
                "state": layout.FAILED_DIR_NAME,
                "file": entry.path.name,
                "attempts": "" if entry.attempts is None else entry.attempts,
                "reason": "",
                "problem": entry.sidecar_error or entry.last_error or "",
            }
            for entry in inbox.failed(supervisor_dir)
        ),
    ]
