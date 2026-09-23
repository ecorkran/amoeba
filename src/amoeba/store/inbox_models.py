"""Closed vocabularies and transfer objects for the inbox and message queue.

Every inbox and message vocabulary value is defined here and nowhere else. Like
``models.py``, this module knows nothing about SQL or ``sqlite3``.

The kind-to-payload-model table is **not** here: payload models are the
submission wire format and live in ``amoeba.inbox.envelope``. ``amoeba.store``
never imports ``amoeba.inbox`` — ``apply_submission`` takes plain,
already-validated values — so the table sits beside the models it names.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Final


class SubmissionKind(StrEnum):
    """What a submission asks the store to do.

    Adding a kind is three things, all of them: a member here, a payload model
    in ``amoeba.inbox.envelope``, and an effect in ``InboxOperations``.
    """

    CREATE_PROJECT = "create_project"
    RESOLUTION = "resolution"
    INTENT = "intent"


#: Payload keys each kind's effect reads, defined once. The envelope's payload
#: models in ``amoeba.inbox`` use these as their field names; a test there pins
#: the two together, so neither side can rename a key alone.
RESOLUTION_BLOCKED_STATE_ID: Final = "blocked_state_id"
RESOLUTION_DETAIL: Final = "detail"
INTENT_NODE_ID: Final = "node_id"
INTENT_BODY: Final = "body"


class SubmissionOutcome(StrEnum):
    """How an attributed submission ended. Both are terminal."""

    APPLIED = "applied"
    REJECTED = "rejected"


class Channel(StrEnum):
    """Which message stream a row belongs to."""

    INTENT = "intent"
    ESCALATION = "escalation"


class QuarantineReason(StrEnum):
    """Why a submission file could not be attributed to an open project store.

    Recorded in the file's ``.reason.json`` sidecar. A submission that *can* be
    attributed ends as a store record instead, never here.
    """

    UNPARSEABLE_ENVELOPE = "unparseable_envelope"
    UNKNOWN_ENVELOPE_VERSION = "unknown_envelope_version"
    UNKNOWN_KIND = "unknown_kind"
    INVALID_PROJECT_ID = "invalid_project_id"
    INVALID_PAYLOAD = "invalid_payload"
    NO_STORE_FOR_PROJECT = "no_store_for_project"


@dataclass(frozen=True)
class SubmissionRecord:
    """One applied or rejected submission.

    ``applied_seq`` is the receiver-assigned order (D4) — authoritative, unlike
    ``submitted_at``, which is the submitter's clock. ``submitted_by`` is
    free-form and never branched on.
    """

    applied_seq: int
    id: str
    project_id: str
    kind: SubmissionKind
    submitted_by: str
    submitted_at: datetime
    payload: Mapping[str, object]
    outcome: SubmissionOutcome
    reason: str | None = None
    applied_at: datetime | None = None


@dataclass(frozen=True)
class Message:
    """One row on a message channel.

    ``seq`` is the replay cursor. An escalation carries ``blocked_state_id``,
    and ``journal_entry_id`` when recovery raised it; an intent carries
    ``submission_id`` as provenance. ``payload`` is opaque to the store.
    """

    seq: int
    id: str
    project_id: str
    channel: Channel
    node_id: str | None = None
    blocked_state_id: str | None = None
    journal_entry_id: str | None = None
    submission_id: str | None = None
    payload: Mapping[str, object] | None = None
    created_at: datetime | None = None
    acknowledged_at: datetime | None = None
    acknowledged_by: str | None = None

    @property
    def is_acknowledged(self) -> bool:
        """Whether a consumer has marked this row consumed."""
        return self.acknowledged_at is not None
