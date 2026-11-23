"""Seeding for the message store tests: members, requests and what they leave."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta

from amoeba.store.messages import insert_request
from amoeba.store.models import Message
from amoeba.store.row_values import encode_timestamp
from amoeba.store.store import Transaction
from store.seed import insert_member, insert_program

NOW = datetime(2026, 11, 9, 12, 0, tzinfo=UTC)
TTL = timedelta(hours=72)
PROGRAM = "demo"
SENDER = "sender-member"
ADDRESSEE = "addressee-member"
THIRD = "third-member"


def seed_members(
    transaction: Transaction,
    *project_ids: str,
    names: Mapping[str, str] | None = None,
) -> None:
    """The program ``demo`` and one active member for each id.

    A member is named by its id unless ``names`` gives it another name."""
    insert_program(
        transaction,
        program_id=PROGRAM,
        concept_member=None,
        concept_path=None,
        registered_at=NOW,
        updated_at=NOW,
    )
    for project_id in project_ids:
        insert_member(
            transaction,
            project_id=project_id,
            program_id=PROGRAM,
            rules_paths=(),
            authorize_allow=(),
            authorize_deny=(),
            registered_at=NOW,
            updated_at=NOW,
            name=None if names is None else names.get(project_id),
        )


def send_request(
    transaction: Transaction,
    message_id: str,
    *,
    from_member: str = SENDER,
    to_member: str = ADDRESSEE,
    parent_id: str | None = None,
    parent_depth: int | None = None,
    now: datetime = NOW,
) -> Message:
    return insert_request(
        transaction,
        message_id=message_id,
        from_member=from_member,
        to_member=to_member,
        parent_id=parent_id,
        parent_depth=parent_depth,
        subject=f"subject of {message_id}",
        body=f"body of {message_id}",
        ttl=TTL,
        now=now,
    )


def insert_raw_note(
    transaction: Transaction, message_id: str, *, changed: datetime
) -> None:
    """A note straight into the table, with no delivery: for tests of reads that must
    ignore a note, where ``store.notes.insert_note`` would add what they do not test."""
    stamp = encode_timestamp(changed)
    transaction.execute(
        "INSERT INTO messages (message_id, kind, from_member, to_member, depth, "
        "subject, body, created_at, state_changed_at, owner_id) "
        "VALUES (?, 'note', ?, ?, 1, 's', 'b', ?, ?, (SELECT owner_id FROM owners))",
        (message_id, SENDER, ADDRESSEE, stamp, stamp),
    )


def delivery_rows(transaction: Transaction) -> list[tuple[int, str, str, str]]:
    """Every delivery as ``(seq, member, message, event)``, in order."""
    return [
        (int(row[0]), str(row[1]), str(row[2]), str(row[3]))
        for row in transaction.execute(
            "SELECT seq, member_id, message_id, event FROM deliveries ORDER BY seq"
        )
    ]


def count(transaction: Transaction, table: str) -> int:
    row = transaction.execute(f"SELECT count(*) FROM {table}").fetchone()
    assert row is not None
    return int(row[0])
