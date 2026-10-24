"""The closed intent vocabulary: kinds, rejection codes, the body model (D1, D3, D4)."""

from __future__ import annotations

from enum import StrEnum
from typing import Final, Self

from pydantic import BaseModel, ConfigDict, model_validator

from amoeba.runner.lifecycle.steps import STEP_MAP, LifecycleStep, StepLevel

#: The longest detail an acknowledgment reason carries after its ``"<code>: "``.
REASON_DETAIL_LIMIT: Final = 512


class IntentKind(StrEnum):
    """What an intent asks of the Runner."""

    DRIVE = "drive"
    EXCLUDE = "exclude"
    PAUSE = "pause"
    RESUME = "resume"
    CLEAR = "clear"


class IntentRejection(StrEnum):
    """Why an intent was rejected. The code leads the acknowledgment reason."""

    MALFORMED_BODY = "malformed_body"
    TARGET_NOT_INITIATIVE_OR_SLICE = "target_not_initiative_or_slice"
    TARGET_UNLINKED = "target_unlinked"
    UNTIL_NOT_APPLICABLE = "until_not_applicable"


class TargetKind(StrEnum):
    """What an intent's target is: the project, an initiative, or a slice."""

    PROJECT = "project"
    INITIATIVE = "initiative"
    SLICE = "slice"


class IntentBody(BaseModel):
    """The payload of an intent message. Unknown keys are errors."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    intent: IntentKind
    until: LifecycleStep | None = None

    @model_validator(mode="after")
    def _until_only_with_drive(self) -> Self:
        if self.until is not None and self.intent is not IntentKind.DRIVE:
            raise ValueError(
                f"until is only valid with drive (got {self.intent.value})"
            )
        return self


def until_applies(target: TargetKind, step: LifecycleStep) -> bool:
    """Whether ``drive until step`` means anything for ``target``.

    A slice has no initiative-level steps, so stopping at one is meaningless there.
    """
    if target is TargetKind.SLICE:
        return STEP_MAP[step].level is StepLevel.SLICE
    return True
