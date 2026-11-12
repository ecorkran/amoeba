"""``dismiss``: close a question that has no answer to deliver (slice 228, D5).

The document is validated here, so the CLI and the MCP layer pass their input through
unchanged. One ``BEGIN IMMEDIATE`` transaction finds the question (by key, or the
run's latest) and closes it by compare-and-set. No subprocess, and the run is not
resumed: it stays paused in Squadron, where Squadron's own commands deal with it.
The reason is stored and returned as data and never reaches a command line.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, ValidationError

from amoeba.config.user_config import NonBlank
from amoeba.operations.reject_codes import validation_problems
from amoeba.store.models import QuestionKey
from amoeba.store.questions import dismiss_question, find_question, latest_answer
from amoeba.store.store import Store
from amoeba.store.vocabulary import ClosedReason, QuestionState, ResumeOutcome


class DismissRequest(BaseModel):
    """What ``dismiss`` is asked: the run, optionally which pause, and why."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: NonBlank
    #: The pause, as ``sq runs wait --json`` printed it; the run's latest question
    #: when omitted.
    paused_at: NonBlank | None = None
    reason: NonBlank


class DismissOutcome(StrEnum):
    DISMISSED = "dismissed"
    UNCHANGED = "unchanged"
    REJECTED = "rejected"


class DismissRejection(StrEnum):
    """Why a dismissal was rejected."""

    NO_SUCH_QUESTION = "no_such_question"
    MALFORMED = "malformed"
    NOT_OPEN = "not_open"


@dataclass(frozen=True)
class DismissResult:
    """The result of ``dismiss``. Fields that do not apply are ``None`` or empty."""

    outcome: DismissOutcome
    rejection: DismissRejection | None = None
    key: QuestionKey | None = None
    #: For ``dismissed`` and ``unchanged``: why the question is closed.
    closed_reason: ClosedReason | None = None
    closed_detail: str | None = None
    problems: tuple[str, ...] = ()


def dismiss(
    store: Store, document: object, *, clock: Callable[[], datetime]
) -> DismissResult:
    """Close the question ``document`` names as dismissed.

    Raises:
        StoreError: The store cannot be used.
    """
    try:
        request = DismissRequest.model_validate(document)
    except ValidationError as error:
        return _rejected(DismissRejection.MALFORMED, validation_problems(error))
    with store.write() as transaction:
        found = find_question(transaction, request.run_id, request.paused_at)
        if found is None:
            return _rejected(
                DismissRejection.NO_SUCH_QUESTION,
                (f"no question for run {request.run_id}",),
            )
        if found.state is QuestionState.CLOSED:
            return DismissResult(
                DismissOutcome.UNCHANGED,
                key=found.key,
                closed_reason=found.closed_reason,
                closed_detail=found.closed_detail,
            )
        if dismiss_question(transaction, found, request.reason, now=clock()):
            return DismissResult(
                DismissOutcome.DISMISSED,
                key=found.key,
                closed_reason=ClosedReason.DISMISSED,
                closed_detail=request.reason,
            )
        # Refused inside the same transaction: an answer already delivered.
        answer = latest_answer(transaction, found.key)
    outcome = None if answer is None else answer.resume_outcome
    return _rejected(
        DismissRejection.NOT_OPEN, (_not_open_text(found.key, outcome),), found.key
    )


def _not_open_text(key: QuestionKey, outcome: ResumeOutcome | None) -> str:
    if outcome is None:
        return (
            f"the answer to {key.run_id} at {key.paused_at} is being delivered (a "
            "resume is in flight); dismiss again once it has ended"
        )
    if outcome is ResumeOutcome.RESUMED:
        return (
            f"the answer to {key.run_id} at {key.paused_at} was delivered and the run "
            "resumed; `retract` stops it being precedent"
        )
    return (
        f"the answer to {key.run_id} at {key.paused_at} was recorded but never "
        "delivered (not_delivered); there is nothing to dismiss"
    )


def _rejected(
    reason: DismissRejection,
    problems: tuple[str, ...],
    key: QuestionKey | None = None,
) -> DismissResult:
    return DismissResult(
        DismissOutcome.REJECTED, rejection=reason, key=key, problems=problems
    )
