"""Rows for the inbox listings: ``inbox``, ``submissions``, and ``messages``.

A sibling of ``inspect.py``, which registers these in its one ``LISTINGS``
registry. Split out to keep that module near its line budget; nothing here is
reachable except through the registry.

``submissions`` and ``messages`` receive a **read-only** store. ``inbox`` reads
the supervisor directory and opens no store at all.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import TYPE_CHECKING

from amoeba import inbox
from amoeba.inbox import layout
from amoeba.store import Channel, Store

if TYPE_CHECKING:  # pragma: no cover - typing only; inspect.py imports this
    from amoeba.cli.inspect import Row


def submission_rows(store: Store, args: argparse.Namespace) -> list[Row]:
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
        for record in store.submissions(args.project)
    ]


def message_rows(store: Store, args: argparse.Namespace) -> list[Row]:
    """Messages for a project in ``seq`` order: one channel, or every one."""
    channels = list(Channel) if args.channel is None else [Channel(args.channel)]
    messages = sorted(
        (
            message
            for channel in channels
            for message in store.messages(args.project, channel=channel)
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
