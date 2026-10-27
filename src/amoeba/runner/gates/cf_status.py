"""CF's gate state from ``cf status --json``, on one ordered scale (slice 128, D1).

CF evaluates only the boundary at the slice's current position, so the Runner reads
``activeSlice.status`` and ``gateInfo`` and maps them onto :class:`GatePosition`,
defined once. The model is lenient about keys CF adds and strict about the fields it
maps. ``rationale`` and ``pendingDecisions`` are evidence for people and are never
matched. Everything here is pure.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import IntEnum, StrEnum
from types import MappingProxyType
from typing import Final

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr, ValidationError

from amoeba.runner.lifecycle.steps import LifecycleStep

_ACTIVE_SLICE_KEY: Final = "activeSlice"


class GatePosition(IntEnum):
    """Where CF's pointer stands in a slice's lifecycle, in order.

    ``PENDING_DECISION`` and ``UNKNOWN`` are off the scale (negative), so an ordered
    comparison against a gate is meaningful only when :attr:`on_scale` is true.
    """

    UNKNOWN = -2
    PENDING_DECISION = -1
    NEEDS_DESIGN = 0
    AT_SLICE_GATE = 1
    PAST_SLICE_GATE = 2
    AT_TASKS_GATE = 3
    PAST_TASKS_GATE = 4
    AT_CODE_GATE = 5
    PAST_CODE_GATE = 6

    @property
    def on_scale(self) -> bool:
        """Whether the position can be ordered against a gate."""
        return self >= GatePosition.NEEDS_DESIGN


class CFStatus(StrEnum):
    """The ``activeSlice.status`` values the Runner maps; any other is ``UNKNOWN``."""

    NEEDS_DESIGN = "needs-design"
    NEEDS_TASKS = "needs-tasks"
    IN_IMPLEMENTATION = "in-implementation"
    COMPLETE = "complete"
    PENDING_REVIEW = "pending-review"
    REVIEW_FAILED = "review-failed"
    PENDING_DECISION = "pending-decision"


class ReviewType(StrEnum):
    """The ``gateInfo.reviewType`` values that name a boundary."""

    SLICE = "slice"
    TASKS = "tasks"
    CODE = "code"


_NO_GATE_POSITION: Final[Mapping[str, GatePosition]] = MappingProxyType(
    {
        CFStatus.NEEDS_DESIGN: GatePosition.NEEDS_DESIGN,
        CFStatus.NEEDS_TASKS: GatePosition.PAST_SLICE_GATE,
        CFStatus.IN_IMPLEMENTATION: GatePosition.PAST_TASKS_GATE,
        CFStatus.COMPLETE: GatePosition.PAST_CODE_GATE,
        CFStatus.PENDING_DECISION: GatePosition.PENDING_DECISION,
    }
)
_AT_GATE_POSITION: Final[Mapping[str, GatePosition]] = MappingProxyType(
    {
        ReviewType.SLICE: GatePosition.AT_SLICE_GATE,
        ReviewType.TASKS: GatePosition.AT_TASKS_GATE,
        ReviewType.CODE: GatePosition.AT_CODE_GATE,
    }
)

#: The gate each pipeline step's review is judged at, once the step has run (D3).
EXIT_GATE: Final[Mapping[LifecycleStep, GatePosition]] = MappingProxyType(
    {
        LifecycleStep.SLICE_DESIGN: GatePosition.AT_SLICE_GATE,
        LifecycleStep.TASKS: GatePosition.AT_TASKS_GATE,
        LifecycleStep.IMPLEMENTATION: GatePosition.AT_CODE_GATE,
    }
)

#: The gate a step must cross before it launches (D5). ``slice_design`` has none.
ENTRY_GATE: Final[Mapping[LifecycleStep, GatePosition]] = MappingProxyType(
    {
        LifecycleStep.TASKS: GatePosition.AT_SLICE_GATE,
        LifecycleStep.IMPLEMENTATION: GatePosition.AT_TASKS_GATE,
    }
)


class _Model(BaseModel):
    # Lenient about keys CF adds: they are ignored, not refused.
    model_config = ConfigDict(extra="ignore", frozen=True, populate_by_name=True)


class GateInfo(_Model):
    """Why CF blocks at a review gate."""

    review_type: StrictStr = Field(alias="reviewType")
    rationale: StrictStr


class PendingDecision(_Model):
    """One design decision still owed to the PM."""

    heading: StrictStr
    line: StrictInt


class CFActiveSlice(_Model):
    """``activeSlice`` of ``cf status --json``: the fields mapped or carried."""

    name: StrictStr
    index: StrictInt | None
    status: StrictStr
    gate_info: GateInfo | None = Field(default=None, alias="gateInfo")
    pending_decisions: tuple[PendingDecision, ...] | None = Field(
        default=None, alias="pendingDecisions"
    )
    gate_exempt: StrictStr | None = Field(default=None, alias="gateExempt")


def parse_status(document: Mapping[str, object]) -> CFActiveSlice | None:
    """The ``activeSlice`` of a ``cf status --json`` document, or ``None``.

    ``None`` means the document does not have the shape the Runner maps; the caller
    treats that as an unreadable gate, never as a default.
    """
    raw = document.get(_ACTIVE_SLICE_KEY)
    if not isinstance(raw, Mapping):
        return None
    try:
        return CFActiveSlice.model_validate(raw)
    except ValidationError:
        # Expected: a field of the wrong type, or a missing one. The answer is None.
        return None


def _normalised(text: str) -> str:
    return text.strip().lower()


def position_of(active_slice: CFActiveSlice) -> GatePosition:
    """Where CF's pointer stands. Anything the table does not name is ``UNKNOWN``."""
    status = _normalised(active_slice.status)
    if status in (CFStatus.PENDING_REVIEW, CFStatus.REVIEW_FAILED):
        info = active_slice.gate_info
        if info is None:
            return GatePosition.UNKNOWN
        return _AT_GATE_POSITION.get(
            _normalised(info.review_type),
            GatePosition.UNKNOWN,
        )
    return _NO_GATE_POSITION.get(status, GatePosition.UNKNOWN)
