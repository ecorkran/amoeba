"""The one table that names every step (262 D3).

A step is written in two places only: its handle (name, request, reply, whether it
writes and needs config) in a ``models_*`` module, listed here, and its function in
``dispatch``. No request model holds a field of a date or time type: the hub stamps
every time with its own clock (D2), and a test walks this table to say so.
"""

from __future__ import annotations

from typing import Any, Final

from amoeba.operations.steps.model_base import Step, StepModel
from amoeba.operations.steps.models_pause import (
    PAUSE_SOURCES,
    QUESTION_CLAIM_HELD,
    QUESTION_HOLD,
    QUESTION_INSERT,
    QUESTION_REPLACE_CLAIM,
    QUESTION_SETTLE,
    QUESTION_WAIT,
)
from amoeba.operations.steps.models_resume import (
    RESUME_CLAIM,
    RESUME_READ,
    RESUME_RECORD,
    ClaimStatus,
    ResumeClaimPayload,
    ResumeClaimReply,
    ResumeClaimRequest,
    ResumeReadReply,
    ResumeReadRequest,
    ResumeRecordReply,
    ResumeRecordRequest,
)

__all__ = [
    "PAUSE_SOURCES",
    "QUESTION_CLAIM_HELD",
    "QUESTION_HOLD",
    "QUESTION_INSERT",
    "QUESTION_REPLACE_CLAIM",
    "QUESTION_SETTLE",
    "QUESTION_WAIT",
    "RESUME_CLAIM",
    "RESUME_READ",
    "RESUME_RECORD",
    "STEP_MODELS",
    "ClaimStatus",
    "ResumeClaimPayload",
    "ResumeClaimReply",
    "ResumeClaimRequest",
    "ResumeReadReply",
    "ResumeReadRequest",
    "ResumeRecordReply",
    "ResumeRecordRequest",
    "Step",
    "StepModel",
]

#: The one table from a step's name to the step.
STEP_MODELS: Final[dict[str, Step[Any, Any]]] = {
    step.name: step
    for step in (
        RESUME_CLAIM,
        RESUME_READ,
        RESUME_RECORD,
        QUESTION_INSERT,
        QUESTION_HOLD,
        QUESTION_CLAIM_HELD,
        QUESTION_REPLACE_CLAIM,
        QUESTION_WAIT,
        QUESTION_SETTLE,
        PAUSE_SOURCES,
    )
}
