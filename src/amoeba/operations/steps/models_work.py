"""``claim_work``'s models: what a machine is handed to start (262 D10)."""

from __future__ import annotations

from typing import Annotated, Final, Literal

from pydantic import Field

from amoeba.operations.steps.model_base import Step, StepModel


class ResumeItem(StepModel):
    """An answer to resume: ``amoeba resume-run <answer seq> <claim id>``."""

    kind: Literal["resume"] = "resume"
    answer_seq: int
    claim_id: str
    run_id: str


class HandlePauseItem(StepModel):
    """A question to handle again: ``amoeba handle-pause <run id>`` in its checkout."""

    kind: Literal["handle_pause"] = "handle_pause"
    run_id: str
    checkout: str


class WakeItem(StepModel):
    """A wake claimed for this machine: ``amoeba wake-run <wake id>``."""

    kind: Literal["wake"] = "wake"
    wake_id: str
    directory: str
    log_stem: str


type WorkItem = Annotated[
    ResumeItem | HandlePauseItem | WakeItem, Field(discriminator="kind")
]


class ClaimWorkRequest(StepModel):
    """The calling machine's logs directory, for a wake's log stem (D8)."""

    logs_dir: str


class ClaimWorkReply(StepModel):
    """At most ``MAX_WORK_PER_CLAIM`` items; the rest wait for the next call."""

    items: tuple[WorkItem, ...]


CLAIM_WORK: Final = Step(
    "claim_work",
    ClaimWorkRequest,
    ClaimWorkReply,
    writes=True,
    keeps_result=True,
    needs_config=True,
)
