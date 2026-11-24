"""The resume steps' models and handles (262 D4, D6)."""

from __future__ import annotations

from enum import StrEnum
from typing import Final

from amoeba.operations.steps.model_base import Step, StepModel
from amoeba.store.vocabulary import ResumeOutcome


class ResumeClaimPayload(StepModel):
    """What a resume needs once it holds the claim (D6)."""

    answer_seq: int
    claim_id: str
    run_id: str
    paused_at: str
    question: str
    checkout: str
    answer_text: str
    resume_wait_seconds: float


class ResumeClaimRequest(StepModel):
    answer_seq: int


class ClaimStatus(StrEnum):
    """The three ways ``resume_claim`` answers."""

    CLAIMED = "claimed"
    IN_FLIGHT = "in_flight"
    FINAL = "final"


class ResumeClaimReply(StepModel):
    """``claimed`` carries the payload; ``final`` carries the stored outcome."""

    status: ClaimStatus
    claim: ResumeClaimPayload | None = None
    final_outcome: ResumeOutcome | None = None
    final_detail: str | None = None
    final_log: str | None = None


class ResumeReadRequest(StepModel):
    answer_seq: int
    claim_id: str


class ResumeReadReply(StepModel):
    """The payload when the claim id is still the answer's, else ``None``."""

    claim: ResumeClaimPayload | None = None


class ResumeRecordRequest(StepModel):
    answer_seq: int
    claim_id: str | None
    outcome: ResumeOutcome
    detail: str | None
    log: str | None


class ResumeRecordReply(StepModel):
    """What the store holds for the answer after the write: this attempt's outcome, or
    the final one that was already there."""

    outcome: ResumeOutcome
    detail: str | None
    log: str | None
    wrote: bool


RESUME_CLAIM: Final = Step(
    "resume_claim", ResumeClaimRequest, ResumeClaimReply, writes=True, needs_config=True
)
RESUME_READ: Final = Step(
    "resume_read", ResumeReadRequest, ResumeReadReply, writes=False, needs_config=True
)
RESUME_RECORD: Final = Step(
    "resume_record",
    ResumeRecordRequest,
    ResumeRecordReply,
    writes=True,
    needs_config=False,
)
