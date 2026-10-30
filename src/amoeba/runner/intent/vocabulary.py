"""The closed intent vocabulary: kinds, rejection codes, the body model (D1, D3, D4).

Slice 132, D7: ``until`` is gone with the lifecycle steps it named, so a body that
still carries it is a malformed body (unknown keys are errors).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final

from pydantic import BaseModel, ConfigDict

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


class TargetKind(StrEnum):
    """What an intent's target is: the project, an initiative, or a slice."""

    PROJECT = "project"
    INITIATIVE = "initiative"
    SLICE = "slice"


class IntentBody(BaseModel):
    """The payload of an intent message. Unknown keys are errors."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    intent: IntentKind
