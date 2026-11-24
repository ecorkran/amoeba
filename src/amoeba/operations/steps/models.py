"""The request and reply of every step, and the one table that names them (262 D3).

A step is written in two places only: its row in ``STEP_MODELS`` and its function in
``dispatch``. No request model holds a field of a date or time type: the hub stamps
every time with its own clock (D2), and a test walks this table to say so.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Final

from pydantic import BaseModel, ConfigDict

from amoeba.store.vocabulary import ResumeOutcome


class StepModel(BaseModel):
    """Base of every step document: closed (no unknown field) and frozen."""

    model_config = ConfigDict(extra="forbid", frozen=True)


@dataclass(frozen=True)
class Step[Request: StepModel, Reply: StepModel]:
    """A step: its name, its two models and how the hub runs it. The type
    parameters let ``Steps.run`` return the reply type of the request it was given."""

    name: str
    request: type[Request]
    reply: type[Reply]
    #: Its transaction is a write, and through the door its reply is kept.
    writes: bool
    #: It reads the hub's ``config.yaml``. The steps that record an end (a resume's
    #: outcome, a wake's pid and end) load none on purpose: a broken config must not
    #: stop an outcome from being recorded (D10).
    needs_config: bool


# --- the resume (D4, D6) --------------------------------------------------


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

#: The one table from a step's name to the step.
STEP_MODELS: Final[dict[str, Step[Any, Any]]] = {
    step.name: step for step in (RESUME_CLAIM, RESUME_READ, RESUME_RECORD)
}
