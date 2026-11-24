"""The pause path's step models: the question claim, settle and source steps
(262 D4). Requests hold no field of a date or time type; a passage's date travels as
the text the store keeps (``encode_timestamp``). Replies may hold times."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Final

from amoeba.answering.values import AnsweringEvidence, DeclineReason, PassageRef
from amoeba.operations.steps.model_base import Step, StepModel
from amoeba.operations.steps.models_resume import ResumeClaimPayload
from amoeba.store.models import (
    Member,
    PmPrecedent,
    Program,
    StandingAnswerRow,
)
from amoeba.store.row_values import decode_timestamp, encode_timestamp
from amoeba.store.vocabulary import RequestState


class PassageRefModel(StepModel):
    """A ``PassageRef`` as it travels: the date is its stored text."""

    id: str
    source: str
    question_id: str | None
    date: str

    @classmethod
    def of(cls, ref: PassageRef) -> PassageRefModel:
        return cls(
            id=ref.id,
            source=ref.source,
            question_id=ref.question_id,
            date=encode_timestamp(ref.date),
        )

    def to_ref(self) -> PassageRef:
        return PassageRef(
            self.id, self.source, self.question_id, decode_timestamp(self.date, "date")
        )


class EvidenceModel(StepModel):
    """``AnsweringEvidence`` as it travels."""

    proposed_answer: str | None = None
    cited: tuple[str, ...] | None = None
    verdict: str | None = None
    reason: str | None = None

    @classmethod
    def of(cls, evidence: AnsweringEvidence) -> EvidenceModel:
        return cls(
            proposed_answer=evidence.proposed_answer,
            cited=evidence.cited,
            verdict=evidence.verdict,
            reason=evidence.reason,
        )

    def to_evidence(self) -> AnsweringEvidence:
        return AnsweringEvidence(
            self.proposed_answer, self.cited, self.verdict, self.reason
        )


def passages_to_models(
    passages: tuple[PassageRef, ...] | None,
) -> tuple[PassageRefModel, ...] | None:
    return None if passages is None else tuple(PassageRefModel.of(p) for p in passages)


def passages_from_models(
    models: tuple[PassageRefModel, ...] | None,
) -> tuple[PassageRef, ...] | None:
    return None if models is None else tuple(m.to_ref() for m in models)


class HeldRequestModel(StepModel):
    """The fields of a ``done`` request that ``request_passage`` takes."""

    request_id: str
    replied_by: str
    done_at: datetime
    result: str
    commit: str | None
    version: str | None


class RequestFacts(StepModel):
    """A request as the hub sees it now: its effective state (``None`` when it is no
    longer stored), its reason, and its result once it is ``done``."""

    request_id: str
    state: RequestState | None
    reason: str | None = None
    held: HeldRequestModel | None = None


# --- the question claim steps (4.1) --------------------------------------------


class QuestionKeyFields(StepModel):
    """The question every claim step names: the run and the pause, as printed."""

    run_id: str
    paused_at: str


class QuestionInsertRequest(QuestionKeyFields):
    """A new row: ``claimed`` with its answering run, or ``waiting_on_pm`` with a
    reason. Exactly one of ``answering_run_id`` and ``waiting_reason`` is set."""

    member_id: str
    question: str
    checkout: str
    slice_label: str | None
    source_commit: str | None
    passages: tuple[PassageRefModel, ...] | None
    answering_run_id: str | None
    waiting_reason: DeclineReason | None
    waiting_detail: str | None


class InsertedReply(StepModel):
    """``inserted`` is false when a row already existed for the key."""

    inserted: bool


class QuestionHoldRequest(QuestionKeyFields):
    member_id: str
    question: str
    checkout: str
    request_id: str


class QuestionHoldReply(StepModel):
    inserted: bool
    request: RequestFacts | None = None


class QuestionClaimHeldRequest(QuestionKeyFields):
    answering_run_id: str
    passages: tuple[PassageRefModel, ...]
    slice_label: str
    source_commit: str


class LossKind(StrEnum):
    """Who won a claim this caller lost: another claim, or an answer or dismissal."""

    CLAIM = "claim"
    ENDED = "ended"


class QuestionClaimHeldReply(StepModel):
    claimed: bool
    lost_to: LossKind | None = None


class QuestionReplaceClaimRequest(QuestionKeyFields):
    old_answering_run_id: str
    new_answering_run_id: str
    passages: tuple[PassageRefModel, ...]


class AppliedReply(StepModel):
    applied: bool


class QuestionWaitRequest(QuestionKeyFields):
    """Move a claim (``answering_run_id`` set) or a held row (``None``) to
    ``waiting_on_pm``."""

    answering_run_id: str | None
    reason: DeclineReason
    detail: str | None
    evidence: EvidenceModel | None


QUESTION_INSERT: Final = Step(
    "question_insert",
    QuestionInsertRequest,
    InsertedReply,
    writes=True,
    needs_config=False,
)
QUESTION_HOLD: Final = Step(
    "question_hold",
    QuestionHoldRequest,
    QuestionHoldReply,
    writes=True,
    needs_config=False,
)
QUESTION_CLAIM_HELD: Final = Step(
    "question_claim_held",
    QuestionClaimHeldRequest,
    QuestionClaimHeldReply,
    writes=True,
    needs_config=False,
)
QUESTION_REPLACE_CLAIM: Final = Step(
    "question_replace_claim",
    QuestionReplaceClaimRequest,
    AppliedReply,
    writes=True,
    needs_config=False,
)
QUESTION_WAIT: Final = Step(
    "question_wait", QuestionWaitRequest, AppliedReply, writes=True, needs_config=False
)


# --- settle and sources (4.3) --------------------------------------------------


class QuestionSettleRequest(QuestionKeyFields):
    """The answerer's answer for the claim ``answering_run_id`` holds. The hub reads the
    question and the member's settings itself and runs the gate."""

    answering_run_id: str
    answer: str
    cited: tuple[str, ...]
    evidence: EvidenceModel


class SettleStatus(StrEnum):
    ANSWERED = "answered"
    WAITING = "waiting"
    SUPERSEDED = "superseded"


class QuestionSettleReply(StepModel):
    """``answered`` carries the answer's seq and the resume claim that drives the
    resume; ``waiting`` the gate's reason and detail."""

    status: SettleStatus
    answer_seq: int | None = None
    claim: ResumeClaimPayload | None = None
    reason: DeclineReason | None = None
    detail: str | None = None


class CheckoutRef(StepModel):
    """A checkout's path and Context Forge id on the calling machine; never its wake
    command, which only ``wake_read`` returns."""

    path: str
    cf_project_id: str


class PauseSourcesRequest(StepModel):
    member_id: str
    #: The request a held question waits on, or ``None``.
    request_id: str | None = None


class PauseSourcesReply(StepModel):
    """What the gather reads from the store (D4): the program, its members, the PM
    precedent, the standing answers and the concept member's checkout here."""

    program: Program
    members: tuple[Member, ...]
    precedent: tuple[PmPrecedent, ...]
    standing: tuple[StandingAnswerRow, ...]
    concept_checkout: CheckoutRef | None
    request: RequestFacts | None


QUESTION_SETTLE: Final = Step(
    "question_settle",
    QuestionSettleRequest,
    QuestionSettleReply,
    writes=True,
    needs_config=True,
)
PAUSE_SOURCES: Final = Step(
    "pause_sources",
    PauseSourcesRequest,
    PauseSourcesReply,
    writes=False,
    needs_config=False,
)
