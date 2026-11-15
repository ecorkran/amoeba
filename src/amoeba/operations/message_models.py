"""``send``, ``inbox``, ``reply`` and ``cancel``: the requests, the limits and the
outcome vocabularies (slice 240, D2, D4, D12).

The request models are validated here from a raw document, so the CLI and the MCP
layer pass their input through unchanged and both doors give the same ``rejected``
result. A text over a limit is refused naming the limit and is never cut. The views
and results are in ``message_results``.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Final, Self

from pydantic import Field, StrictInt, StrictStr, field_validator, model_validator

from amoeba.operations.release_fields import (
    Version,
    bounded_text,
    full_commit_hash,
    tag_name,
)
from amoeba.operations.set_up_models import FrozenModel, NonBlankText

#: Text limits (D12). Stated in ``docs/cli-contract.md``; each is the most a field may
#: carry, in characters. Text goes to other agents' context, so it has a bound.
MAX_ID_LENGTH: Final = 64
MAX_SUBJECT_LENGTH: Final = 200
MAX_BODY_LENGTH: Final = 4000
#: A ``done`` result and a decline's text (``reply`` carries both as ``text``).
MAX_RESULT_LENGTH: Final = 4000
MAX_REASON_LENGTH: Final = 1000

#: What a ``message_rejections`` row keeps of the text the caller gave (the id, the
#: recipient, the parent and the detail): longer text is cut and ends in ``…``. Unlike a
#: request's text, a rejection's is never read back as the message, only shown.
MAX_RECORDED_LENGTH: Final = 500

#: Retention caps, so what ``inbox``, ``status`` and ``list`` read is bounded by how
#: it is written. A member keeps its newest ``MAX_REJECTIONS_PER_MEMBER`` rejection
#: rows (older ones are dropped as new ones arrive). A sender keeps at most
#: ``MAX_REQUESTS_PER_SENDER`` requests: a ``send`` that would pass it first drops the
#: sender's oldest finished requests, and is rejected ``too_many_open`` only when every
#: one of them is still open or accepted.
MAX_REJECTIONS_PER_MEMBER: Final = 100
MAX_REQUESTS_PER_SENDER: Final = 200

#: A request id: starts with a letter or digit, then letters, digits, ``.``, ``_``,
#: ``-``. The length is the separate limit above, so an over-long id names it. The
#: anchors are needed: a pydantic ``pattern`` searches, it does not match the whole.
_ID_PATTERN: Final = r"^[A-Za-z0-9][A-Za-z0-9._-]*$"

#: The sender's id: kept exactly as given, never stripped or cut.
RequestId = Annotated[
    StrictStr, Field(min_length=1, max_length=MAX_ID_LENGTH, pattern=_ID_PATTERN)
]
_Subject = Annotated[StrictStr, bounded_text(MAX_SUBJECT_LENGTH)]
_Body = Annotated[StrictStr, bounded_text(MAX_BODY_LENGTH)]
_ReplyText = Annotated[StrictStr, bounded_text(MAX_RESULT_LENGTH)]
_Reason = Annotated[StrictStr, bounded_text(MAX_REASON_LENGTH)]


class ReplyAction(StrEnum):
    """What the addressee does with a request (D4)."""

    ACCEPT = "accept"
    DECLINE = "decline"
    DONE = "done"


class SendOutcome(StrEnum):
    """How a ``send`` call ended."""

    SENT = "sent"
    #: The same id with the same content, not ended: nothing changed (D2).
    UNCHANGED = "unchanged"
    REJECTED = "rejected"


class InboxOutcome(StrEnum):
    """How an ``inbox`` call ended."""

    LISTED = "listed"
    REJECTED = "rejected"


class ReplyOutcome(StrEnum):
    """How a ``reply`` call ended."""

    APPLIED = "applied"
    REJECTED = "rejected"


class CancelOutcome(StrEnum):
    """How a ``cancel`` call ended."""

    CANCELLED = "cancelled"
    REJECTED = "rejected"


class SendRequest(FrozenModel):
    """A request to send to another member (D2, D3)."""

    id: RequestId
    #: A Context Forge project name or id: the addressee.
    to: NonBlankText
    subject: _Subject
    body: _Body
    #: The request this one serves; it must exist (D8).
    parent: RequestId | None = None
    #: A Context Forge project name or id; only from a directory in no member (D3).
    member: NonBlankText | None = None


class InboxRequest(FrozenModel):
    """What a member has been sent, and what changed since a delivery number (D7)."""

    #: The ``as_of_seq`` of an earlier call; omitted lists every held request.
    since: Annotated[StrictInt, Field(ge=0)] | None = None
    member: NonBlankText | None = None


class ReplyRequest(FrozenModel):
    """The addressee's answer to a request (D4)."""

    id: RequestId
    action: ReplyAction
    #: The ``done`` result or the decline's reason; required by those two actions.
    text: _ReplyText | None = None
    #: The commit that did the work; ``done`` only, a full hash.
    commit: StrictStr | None = None
    #: The version that carries the work; ``done`` only.
    version: Version | None = None
    member: NonBlankText | None = None

    @field_validator("commit")
    @classmethod
    def _full_hash(cls, value: str | None) -> str | None:
        return None if value is None else full_commit_hash(value)

    @field_validator("version")
    @classmethod
    def _tag_name(cls, value: str | None) -> str | None:
        return tag_name(value)

    @model_validator(mode="after")
    def _action_rules(self) -> Self:
        needs_text = self.action in (ReplyAction.DECLINE, ReplyAction.DONE)
        problems: list[str] = []
        if needs_text and self.text is None:
            problems.append(f"text is required for {self.action.value}")
        if self.action is ReplyAction.ACCEPT and self.text is not None:
            problems.append("text is not allowed for accept")
        problems += [
            f"{name} is only allowed for done"
            for name in ("commit", "version")
            if self.action is not ReplyAction.DONE and getattr(self, name) is not None
        ]
        if problems:
            raise ValueError("; ".join(problems))
        return self


class CancelRequest(FrozenModel):
    """End a request that is open or accepted (D3, D4)."""

    id: RequestId
    reason: _Reason | None = None
    member: NonBlankText | None = None
