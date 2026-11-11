"""``mark_read``: move the PM's marker forward to the last record they saw
(slice 224, D7).

There is no "mark all": ``through`` must be a ``seq`` the caller was shown, normally
the ``read_through`` of a ``decisions`` call, so a record written afterwards has a
higher ``seq`` and stays unread. The marker never moves backward.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, StrictInt, ValidationError

from amoeba.operations.reject_codes import RejectCode, validation_problems
from amoeba.store.decisions import MarkerMove, advance_marker
from amoeba.store.store import Store


class MarkReadRequest(BaseModel):
    """What ``mark_read`` is asked: the last ``seq`` the caller saw."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    through: StrictInt = Field(ge=0)


class MarkReadOutcome(StrEnum):
    MOVED = "moved"
    UNCHANGED = "unchanged"
    REJECTED = "rejected"


class MarkReadResult(BaseModel):
    """The result of ``mark_read``. ``previous`` and ``current`` are null when the
    request was malformed and the marker was not read."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    outcome: MarkReadOutcome
    rejection: RejectCode | None = None
    previous: int | None = None
    current: int | None = None
    problems: tuple[str, ...] = ()


_OUTCOME_OF_MOVE = {
    MarkerMove.MOVED: MarkReadOutcome.MOVED,
    MarkerMove.UNCHANGED: MarkReadOutcome.UNCHANGED,
}


def mark_read(store: Store, document: object) -> MarkReadResult:
    """Advance the marker to ``document``'s ``through``.

    Raises:
        StoreError: The store cannot be used.
    """
    try:
        request = MarkReadRequest.model_validate(document)
    except ValidationError as error:
        return MarkReadResult(
            outcome=MarkReadOutcome.REJECTED,
            rejection=RejectCode.MALFORMED,
            problems=validation_problems(error),
        )
    result = advance_marker(store, request.through)
    if result.move is MarkerMove.BEYOND_LAST_RECORD:
        return MarkReadResult(
            outcome=MarkReadOutcome.REJECTED,
            rejection=RejectCode.BEYOND_LAST_RECORD,
            previous=result.previous,
            current=result.current,
            problems=(
                f"through {request.through} is beyond the last recorded answer; "
                "give the read_through of a decisions call",
            ),
        )
    return MarkReadResult(
        outcome=_OUTCOME_OF_MOVE[result.move],
        previous=result.previous,
        current=result.current,
    )
