"""``answer``: record the PM's answer to a question, then resume the run
(slice 223, D9).

The document is validated here, so the CLI and the MCP layer pass their input through
unchanged. A PM answer skips the reserved-term screen and the answer limit. The write
is one transaction that adds a ``pm`` answer row and sets the question ``answered``
from any state; ``waiting_reason`` and ``waiting_detail`` stay as they were. The newest
PM answer is precedent, which also covers overriding an automatic answer. If the
resume cannot start because ``sq`` cannot be read, the answer stays recorded and the
error propagates: the next call delivers it.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    StrictStr,
    StringConstraints,
    ValidationError,
)

from amoeba.config.user_config import UserConfig
from amoeba.operations.deps import Deps
from amoeba.operations.pause_models import ResumeResult
from amoeba.operations.resume import resume
from amoeba.store.answers import add_pm_answer
from amoeba.store.models import QuestionKey, QuestionRecord
from amoeba.store.questions import get_question, latest_question
from amoeba.store.store import Store, Transaction

#: A stripped, non-empty string.
_NonBlank = Annotated[StrictStr, StringConstraints(strip_whitespace=True, min_length=1)]


class AnswerRequest(BaseModel):
    """What ``answer`` is asked: the run, optionally which pause, and the text."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: _NonBlank
    #: The pause, as ``sq runs wait --json`` printed it; the run's latest question
    #: when omitted.
    paused_at: _NonBlank | None = None
    text: _NonBlank


class AnswerOutcome(StrEnum):
    RECORDED = "recorded"
    REJECTED = "rejected"


class AnswerRejection(StrEnum):
    """Why an answer was rejected."""

    NO_SUCH_QUESTION = "no_such_question"
    MALFORMED = "malformed"


@dataclass(frozen=True)
class AnswerResult:
    """The result of ``answer``. Fields that do not apply are ``None`` or empty."""

    outcome: AnswerOutcome
    rejection: AnswerRejection | None = None
    key: QuestionKey | None = None
    answer_seq: int | None = None
    resume: ResumeResult | None = None
    problems: tuple[str, ...] = ()


def answer(
    store: Store, config: UserConfig, document: object, *, deps: Deps
) -> AnswerResult:
    """Record the PM's answer for the question ``document`` names, then resume.

    Raises:
        SquadronError: ``sq`` could not be read when the run was resumed (the answer
            is already recorded).
        StoreError: The store cannot be used.
    """
    try:
        request = AnswerRequest.model_validate(document)
    except ValidationError as error:
        return _rejected(AnswerRejection.MALFORMED, _problems(error))
    with store.read() as transaction:
        found = _find(transaction, request)
    if found is None:
        return _rejected(
            AnswerRejection.NO_SUCH_QUESTION,
            (
                f"no question for run {request.run_id}: run `amoeba handle_pause "
                f"{request.run_id}` from the run's checkout first",
            ),
        )
    with store.write() as transaction:
        seq = add_pm_answer(transaction, found.key, request.text, now=deps.clock())
    with store.read() as transaction:
        recorded = get_question(transaction, found.key)
    if recorded is None:
        raise ValueError(f"question {found.key} vanished after its answer was added")
    resumed = resume(
        store, recorded, seq, deps=deps, wait_seconds=config.resume_wait_seconds
    )
    return AnswerResult(
        AnswerOutcome.RECORDED, key=found.key, answer_seq=seq, resume=resumed
    )


def _find(transaction: Transaction, request: AnswerRequest) -> QuestionRecord | None:
    if request.paused_at is not None:
        return get_question(transaction, QuestionKey(request.run_id, request.paused_at))
    return latest_question(transaction, request.run_id)


def _rejected(reason: AnswerRejection, problems: tuple[str, ...]) -> AnswerResult:
    return AnswerResult(AnswerOutcome.REJECTED, rejection=reason, problems=problems)


def _problems(error: ValidationError) -> tuple[str, ...]:
    return tuple(
        f"{'.'.join(str(part) for part in problem['loc'])}: {problem['msg']}"
        for problem in error.errors()
    )
