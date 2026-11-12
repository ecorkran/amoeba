"""``retract``: stop a PM answer being precedent (slice 228, D6).

The answer stays delivered and stays in ``decisions`` with ``retracted_at`` and
``retract_reason``; an automatic answer is never precedent, so it is rejected. A new
PM answer to the same question is the undo. The document is validated here, one
``BEGIN IMMEDIATE`` transaction writes, and no subprocess runs.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, StrictInt, ValidationError

from amoeba.answering.values import AnsweredBy
from amoeba.config.user_config import NonBlank
from amoeba.operations.reject_codes import validation_problems
from amoeba.store.models import QuestionKey
from amoeba.store.questions import get_answer, retract_answer
from amoeba.store.store import Store


class RetractRequest(BaseModel):
    """What ``retract`` is asked: the answer's ``seq`` (from ``decisions``) and why."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    answer_seq: StrictInt
    reason: NonBlank


class RetractOutcome(StrEnum):
    RETRACTED = "retracted"
    UNCHANGED = "unchanged"
    REJECTED = "rejected"


class RetractRejection(StrEnum):
    """Why a retraction was rejected."""

    NO_SUCH_ANSWER = "no_such_answer"
    NOT_A_PM_ANSWER = "not_a_pm_answer"
    MALFORMED = "malformed"


@dataclass(frozen=True)
class RetractResult:
    """The result of ``retract``. Fields that do not apply are ``None`` or empty."""

    outcome: RetractOutcome
    rejection: RetractRejection | None = None
    answer_seq: int | None = None
    key: QuestionKey | None = None
    problems: tuple[str, ...] = ()


def retract(
    store: Store, document: object, *, clock: Callable[[], datetime]
) -> RetractResult:
    """Mark the PM answer ``document`` names as retracted.

    Raises:
        StoreError: The store cannot be used.
    """
    try:
        request = RetractRequest.model_validate(document)
    except ValidationError as error:
        return _rejected(RetractRejection.MALFORMED, validation_problems(error))
    seq = request.answer_seq
    with store.write() as transaction:
        found = get_answer(transaction, seq)
        if found is None:
            return _rejected(RetractRejection.NO_SUCH_ANSWER, (f"no answer {seq}",))
        if found.answered_by is not AnsweredBy.PM:
            return _rejected(
                RetractRejection.NOT_A_PM_ANSWER,
                (
                    f"answer {seq} was given automatically: "
                    "only PM answers are precedent",
                ),
                found.key,
            )
        won = retract_answer(transaction, seq, request.reason, now=clock())
    outcome = RetractOutcome.RETRACTED if won else RetractOutcome.UNCHANGED
    return RetractResult(outcome, answer_seq=seq, key=found.key)


def _rejected(
    reason: RetractRejection,
    problems: tuple[str, ...],
    key: QuestionKey | None = None,
) -> RetractResult:
    return RetractResult(
        RetractOutcome.REJECTED, rejection=reason, key=key, problems=problems
    )
