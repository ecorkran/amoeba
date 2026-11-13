"""``answer``: record the PM's answer to a question, then resume the run
(slice 223, D9).

The document is validated here, so the CLI and the MCP layer pass their input through
unchanged. A PM answer skips the reserved-term screen and the answer limit. The write
is one transaction that adds a ``pm`` answer row and sets the question ``answered``
from any state; ``waiting_reason`` and ``waiting_detail`` stay as they were. The newest
PM answer is precedent, which also covers overriding an automatic answer. The answer
and the resume are two steps: if ``sq`` cannot be read when the run is resumed, the
answer stays recorded and the resume is recorded as ``refused`` with the reason, so
the result says what happened and the next ``handle_pause`` delivers the answer.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from pydantic import (
    BaseModel,
    ConfigDict,
    ValidationError,
)

from amoeba.config.user_config import NonBlank, UserConfig
from amoeba.operations.deps import Deps
from amoeba.operations.pause_models import ResumeResult
from amoeba.operations.resume import resume
from amoeba.store.answers import add_pm_answer, record_resume
from amoeba.store.models import QuestionKey
from amoeba.store.questions import find_question, get_question
from amoeba.store.store import Store
from amoeba.store.vocabulary import Door, ResumeOutcome
from amoeba.upstream.squadron.errors import SquadronError


class AnswerRequest(BaseModel):
    """What ``answer`` is asked: the run, optionally which pause, and the text."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: NonBlank
    #: The pause, as ``sq runs wait --json`` printed it; the run's latest question
    #: when omitted.
    paused_at: NonBlank | None = None
    text: NonBlank


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
    store: Store, config: UserConfig, document: object, *, deps: Deps, via: Door
) -> AnswerResult:
    """Record the PM's answer for the question ``document`` names, then resume.

    ``via`` is the door that carried the call (226 D11): set by the door, never by
    the request, and recorded beside the answer. It changes no outcome.

    Raises:
        StoreError: The store cannot be used.
    """
    try:
        request = AnswerRequest.model_validate(document)
    except ValidationError as error:
        return _rejected(AnswerRejection.MALFORMED, _problems(error))
    # One transaction: find the question, add the answer and read the question back,
    # so the answer is recorded against exactly the row it was found on.
    with store.write() as transaction:
        found = find_question(transaction, request.run_id, request.paused_at)
        if found is None:
            return _rejected(
                AnswerRejection.NO_SUCH_QUESTION,
                (
                    f"no question for run {request.run_id}: run `amoeba handle_pause "
                    f"{request.run_id}` from the run's checkout first",
                ),
            )
        seq = add_pm_answer(
            transaction, found.key, request.text, now=deps.clock(), via=via
        )
        recorded = get_question(transaction, found.key)
    if recorded is None:
        raise ValueError(f"question {found.key} vanished after its answer was added")
    try:
        resumed = resume(
            store, recorded, seq, deps=deps, wait_seconds=config.resume_wait_seconds
        )
    except SquadronError as error:
        # Expected: the answer is already recorded, so report the resume as refused
        # (retried by the next ``handle_pause``) rather than lose the result.
        resumed = _record_refused(store, seq, str(error), deps)
    return AnswerResult(
        AnswerOutcome.RECORDED, key=found.key, answer_seq=seq, resume=resumed
    )


def _record_refused(
    store: Store, answer_seq: int, detail: str, deps: Deps
) -> ResumeResult:
    with store.write() as transaction:
        record_resume(
            transaction,
            answer_seq,
            ResumeOutcome.REFUSED,
            detail=detail,
            log=None,
            at=deps.clock(),
        )
    return ResumeResult(ResumeOutcome.REFUSED, detail, None)


def _rejected(reason: AnswerRejection, problems: tuple[str, ...]) -> AnswerResult:
    return AnswerResult(AnswerOutcome.REJECTED, rejection=reason, problems=problems)


def _problems(error: ValidationError) -> tuple[str, ...]:
    return tuple(
        f"{'.'.join(str(part) for part in problem['loc'])}: {problem['msg']}"
        for problem in error.errors()
    )
