"""The wake wrapper's step models (262 D4, D8, D11)."""

from __future__ import annotations

from typing import Final

from amoeba.operations.steps.model_base import Step, StepModel
from amoeba.store.vocabulary import WakeOutcome


class WakeToRun(StepModel):
    """What the wrapper starts: the checkout, the command and how long the wake has
    left on the hub's clock (the wrapper waits that long on its own monotonic clock)."""

    directory: str
    command: str
    seconds_left: float


class WakeReadRequest(StepModel):
    wake_id: str


class WakeReadReply(StepModel):
    """``wake`` when this machine's unended row has no command yet; else ``problem``,
    the reason nothing can run."""

    wake: WakeToRun | None = None
    problem: str | None = None


class WakeSetPidRequest(StepModel):
    wake_id: str
    pid: int


class WakeSetPidReply(StepModel):
    """``recorded`` is false when another run of the wake recorded its pid first, or
    the row ended."""

    recorded: bool


class WakeFinishRequest(StepModel):
    wake_id: str
    outcome: WakeOutcome
    exit_code: int | None
    detail: str | None


class WakeFinishReply(StepModel):
    """``ended`` is false when the row had already ended: its record stands."""

    ended: bool


WAKE_READ: Final = Step(
    "wake_read",
    WakeReadRequest,
    WakeReadReply,
    writes=False,
    keeps_result=False,
    needs_config=False,
)
WAKE_SET_PID: Final = Step(
    "wake_set_pid",
    WakeSetPidRequest,
    WakeSetPidReply,
    writes=True,
    keeps_result=True,
    needs_config=False,
)
WAKE_FINISH: Final = Step(
    "wake_finish",
    WakeFinishRequest,
    WakeFinishReply,
    writes=True,
    keeps_result=True,
    needs_config=False,
)
