"""Pin the inbox and message vocabularies before SQL or parsing depends on them.

Each enum's member set is asserted exactly, so adding or renaming a value fails
here and has to be done on purpose. The every-kind-has-a-payload-model check
lives with the payload models in ``tests/inbox/``, because the table it covers
belongs to ``amoeba.inbox.envelope``, not the store.
"""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime
from enum import StrEnum

import pytest

from amoeba.store.inbox_models import (
    Channel,
    Message,
    QuarantineReason,
    SubmissionKind,
    SubmissionOutcome,
    SubmissionRecord,
)


@pytest.mark.parametrize(
    ("vocabulary", "expected"),
    [
        (SubmissionKind, {"create_project", "resolution", "intent", "verdict"}),
        (SubmissionOutcome, {"applied", "rejected"}),
        (Channel, {"intent", "escalation"}),
        (
            QuarantineReason,
            {
                "unparseable_envelope",
                "unknown_envelope_version",
                "unknown_kind",
                "invalid_project_id",
                "invalid_payload",
                "no_store_for_project",
            },
        ),
    ],
)
def test_vocabulary_members_are_exact(
    vocabulary: type[StrEnum], expected: set[str]
) -> None:
    """A member added or renamed without deliberate intent fails here."""
    assert {member.value for member in vocabulary} == expected


def test_submission_record_is_frozen() -> None:
    record = SubmissionRecord(
        applied_seq=1,
        id="sub-1",
        project_id="demo",
        kind=SubmissionKind.INTENT,
        submitted_by="someone",
        submitted_at=datetime.now(UTC),
        payload={},
        outcome=SubmissionOutcome.APPLIED,
    )

    with pytest.raises(dataclasses.FrozenInstanceError):
        record.outcome = SubmissionOutcome.REJECTED  # type: ignore[misc]


def test_message_is_frozen() -> None:
    message = Message(seq=1, id="msg-1", project_id="demo", channel=Channel.INTENT)

    with pytest.raises(dataclasses.FrozenInstanceError):
        message.seq = 2  # type: ignore[misc]


def test_message_acknowledgement_is_derived_from_the_timestamp() -> None:
    unread = Message(seq=1, id="msg-1", project_id="demo", channel=Channel.INTENT)
    read = dataclasses.replace(unread, acknowledged_at=datetime.now(UTC))

    assert not unread.is_acknowledged
    assert read.is_acknowledged
