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
    PAUSE_BEGIN,
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
from amoeba.operations.steps.models_runs import OPEN_RUNS
from amoeba.operations.steps.models_session import SESSION_END, SESSION_TICK
from amoeba.operations.steps.models_wake import WAKE_FINISH, WAKE_READ, WAKE_SET_PID
from amoeba.operations.steps.models_work import CLAIM_WORK

__all__ = [
    "CLAIM_WORK",
    "OPEN_RUNS",
    "WAKE_FINISH",
    "WAKE_READ",
    "WAKE_SET_PID",
    "PAUSE_BEGIN",
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
    "SESSION_END",
    "SESSION_TICK",
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
        PAUSE_BEGIN,
        WAKE_READ,
        WAKE_SET_PID,
        WAKE_FINISH,
        OPEN_RUNS,
        CLAIM_WORK,
        SESSION_TICK,
        SESSION_END,
    )
}
