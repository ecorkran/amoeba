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

Slice 262 splits it as 261 split its operations: ``record_answer`` is the hub part (it
records the answer and looks at the question's machine, D7) and ``run_recorded_answer``
is the client part, which runs the resume on the claim the hub part took.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from typing import Final

from pydantic import (
    BaseModel,
    ConfigDict,
    ValidationError,
)

from amoeba.config.user_config import NonBlank, UserConfig
from amoeba.operations.deps import Deps
from amoeba.operations.names import PROGRAM_NAME, OperationName
from amoeba.operations.pause_models import ResumeResult
from amoeba.operations.resume import ResumeUnreadableError, resume
from amoeba.operations.steps.dispatch import StepEdges
from amoeba.operations.steps.limits import resume_claim_seconds
from amoeba.operations.steps.models import ResumeClaimPayload
from amoeba.operations.steps.resume import ResumeClaimed, claim_payload, claim_resume
from amoeba.operations.store_steps import LocalSteps, Steps
from amoeba.store.answers import add_pm_answer, mark_not_delivered
from amoeba.store.errors import StoreRowError
from amoeba.store.machines import question_machine
from amoeba.store.models import QuestionKey, QuestionRecord
from amoeba.store.questions import find_question, get_question
from amoeba.store.row_values import encode_timestamp
from amoeba.store.store import Store, Transaction
from amoeba.store.vocabulary import Door, ResumeOutcome


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
class WaitingOnMachine:
    """The run is on another machine: the answer waits for that machine's next call
    (262 D7). ``last_called_at`` is the hub's time as text, or ``None`` when that
    machine has never called."""

    machine: str
    last_called_at: str | None


@dataclass(frozen=True)
class AnswerResult:
    """The result of ``answer``. Fields that do not apply are ``None`` or empty."""

    outcome: AnswerOutcome
    rejection: AnswerRejection | None = None
    key: QuestionKey | None = None
    answer_seq: int | None = None
    resume: ResumeResult | None = None
    problems: tuple[str, ...] = ()
    #: Set when the question's run is on another machine (D7).
    waiting_on_machine: WaitingOnMachine | None = None


@dataclass(frozen=True)
class AnswerRecorded:
    """The hub part's result: ``result`` as far as the hub could take it, and the
    resume claim when the run is on the calling machine, which then runs it."""

    result: AnswerResult
    claim: ResumeClaimPayload | None = None


#: The detail of an answer to a question whose machine was removed (D7, D13).
MACHINE_REMOVED_DETAIL: Final = (
    "the machine the run was on was removed, so the answer cannot be delivered"
)


def answer(
    store: Store, config: UserConfig, document: object, *, deps: Deps, via: Door
) -> AnswerResult:
    """Record the PM's answer for the question ``document`` names, then resume, both
    in process: the hub part on ``store``, then the client part on a ``LocalSteps``.

    ``via`` is the door that carried the call (226 D11): set by the door, never by
    the request, and recorded beside the answer. It changes no outcome.

    Raises:
        StoreError: The store cannot be used.
        SquadronError: The first poll could not be read and an earlier attempt's file
            holds ``started`` (the answer stays recorded).
    """
    recorded = record_answer(store, config, document, now=deps.clock(), via=via)
    steps = LocalSteps(store, StepEdges(deps.clock, lambda: config))
    return run_recorded_answer(steps, recorded, deps)


def record_answer(
    store: Store,
    config: UserConfig,
    document: object,
    *,
    now: datetime,
    via: Door,
) -> AnswerRecorded:
    """The hub part: validate, record the answer and look at the question's machine,
    in today's one transaction (262 D7).

    Raises:
        StoreError: The store cannot be used.
    """
    try:
        request = AnswerRequest.model_validate(document)
    except ValidationError as error:
        return AnswerRecorded(_rejected(AnswerRejection.MALFORMED, _problems(error)))
    # One transaction: find the question, add the answer and read the question back,
    # so the answer is recorded against exactly the row it was found on.
    with store.write() as transaction:
        found = find_question(transaction, request.run_id, request.paused_at)
        if found is None:
            return AnswerRecorded(
                _rejected(
                    AnswerRejection.NO_SUCH_QUESTION,
                    (
                        f"no question for run {request.run_id}: run "
                        f"`{PROGRAM_NAME} {OperationName.HANDLE_PAUSE.cli_name} "
                        f"{request.run_id}` from the run's checkout first",
                    ),
                )
            )
        seq = add_pm_answer(transaction, found.key, request.text, now=now, via=via)
        recorded = get_question(transaction, found.key)
        if recorded is None:
            raise ValueError(
                f"question {found.key} vanished after its answer was added"
            )
        return _by_machine(transaction, config, recorded, seq, now)


def _by_machine(
    transaction: Transaction,
    config: UserConfig,
    question: QuestionRecord,
    answer_seq: int,
    now: datetime,
) -> AnswerRecorded:
    """D7's table: what the hub does by the machine the question's run is on."""
    key = question.key
    base = AnswerResult(AnswerOutcome.RECORDED, key=key, answer_seq=answer_seq)
    where = question_machine(transaction, key.run_id, key.paused_at)
    if where is None:
        raise ValueError(f"question {key} vanished after its answer was added")
    if where.machine_id is None:
        mark_not_delivered(transaction, answer_seq, MACHINE_REMOVED_DETAIL, now=now)
        undelivered = ResumeResult(
            ResumeOutcome.NOT_DELIVERED, MACHINE_REMOVED_DETAIL, None
        )
        return AnswerRecorded(replace(base, resume=undelivered))
    if where.machine_id != transaction.acting("answers").machine_id:
        if where.name is None:
            raise AssertionError("a question with a machine id has that machine's name")
        waiting = WaitingOnMachine(
            where.name,
            None
            if where.last_called_at is None
            else encode_timestamp(where.last_called_at),
        )
        return AnswerRecorded(replace(base, waiting_on_machine=waiting))
    claim = claim_resume(transaction, answer_seq, now, resume_claim_seconds(config))
    if not isinstance(claim, ResumeClaimed):
        raise StoreRowError(f"the new answer {answer_seq} could not be claimed")
    payload = claim_payload(
        transaction, answer_seq, claim.claim_id, float(config.resume_wait_seconds)
    )
    return AnswerRecorded(base, payload)


def run_recorded_answer(
    steps: Steps, recorded: AnswerRecorded, deps: Deps
) -> AnswerResult:
    """The client part: run the resume the hub part handed over, or return its result.

    An unreadable first poll returns the refused result (the resume recorded it); a
    ``started`` attempt file makes ``resume`` raise ``SquadronError``, which stays
    raised because nothing may be recorded then (262 D6).

    Raises:
        SquadronError: See above.
        HubUnreachableError, HubRefusedError: A step got no reply, or was refused.
    """
    if recorded.claim is None:
        return recorded.result
    try:
        resumed = resume(steps, recorded.claim, deps)
    except ResumeUnreadableError as unreadable:
        resumed = unreadable.result
    return replace(recorded.result, resume=resumed)


def _rejected(reason: AnswerRejection, problems: tuple[str, ...]) -> AnswerResult:
    return AnswerResult(AnswerOutcome.REJECTED, rejection=reason, problems=problems)


def _problems(error: ValidationError) -> tuple[str, ...]:
    return tuple(
        f"{'.'.join(str(part) for part in problem['loc'])}: {problem['msg']}"
        for problem in error.errors()
    )
