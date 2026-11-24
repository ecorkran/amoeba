"""``amoeba resume-run``: the body of a resume that another call's work claim handed out
(slice 262, D6, D10).

``work_start`` starts it detached, so a resume that another call claimed never blocks
that call. It reads the claim's payload (``resume_read``, which gives nothing once the
claim id is no longer the answer's) and resumes on it (``resume``), which records the
outcome. It runs no after-step.
"""

from __future__ import annotations

from typing import Final

from amoeba.operations.deps import Deps
from amoeba.operations.pause_models import ResumeResult
from amoeba.operations.resume import resume
from amoeba.operations.steps.models import RESUME_READ
from amoeba.operations.steps.models_resume import ResumeReadRequest
from amoeba.operations.store_steps import Steps

#: The ``amoeba`` subcommand, defined once because the CLI imports from the operations.
RESUME_RUN_COMMAND: Final = "resume-run"


def run_resume(
    steps: Steps, deps: Deps, answer_seq: int, claim_id: str
) -> ResumeResult | None:
    """Resume the answer on its claim; ``None`` when ``claim_id`` is no longer the
    answer's (it ran out and was taken again, or an outcome cleared it): nothing is
    started.

    Raises:
        ResumeUnreadableError, SquadronError: See ``resume``.
        HubUnreachableError, HubRefusedError: A step got no reply, or was refused.
    """
    read = steps.run(
        RESUME_READ, ResumeReadRequest(answer_seq=answer_seq, claim_id=claim_id)
    )
    if read.claim is None:
        return None
    return resume(steps, read.claim, deps)
