"""The ``origin`` rules of ``add`` (slice 261, D7 step 1). Read-only.

Record when the member has none and no active member has it; keep when the checkout
has none; replace when they differ. Another active member having the new ``origin``
refuses a replace as ``origin_taken``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from amoeba.operations.add_names import refusal
from amoeba.operations.set_up_models import SetUpProblem, SetUpProblemCode
from amoeba.store.member_names import active_member_by_origin
from amoeba.store.models import Member
from amoeba.store.store import Transaction


class OriginAction(StrEnum):
    """What the call does to the member's ``origin``."""

    RECORD = "record"
    REPLACE = "replace"


@dataclass(frozen=True)
class OriginChange:
    action: OriginAction
    #: The member's ``origin`` before (``None`` for a record); reduced forms only.
    old: str | None
    new: str


def origin_change(
    transaction: Transaction, member: Member, origin: str | None, *, strict: bool
) -> OriginChange | SetUpProblem | None:
    """The three rules for a member and the checkout's ``origin`` (D7 step 1).

    Record when the member has none and no active member has it; keep when the
    checkout has none; replace when they differ. Another active member having the
    new ``origin`` refuses a replace as ``origin_taken``, and a record too when
    ``strict`` (``--attach-to``).
    """
    if origin is None or origin == member.origin:
        return None
    holder = active_member_by_origin(transaction, origin)
    if holder is not None and holder.project_id != member.project_id:
        if member.origin is None and not strict:
            return None
        return refusal(
            SetUpProblemCode.ORIGIN_TAKEN,
            f"this checkout's origin {origin} is also member {holder.name!r}'s, and "
            f"member {member.name!r} would take it, so the two are now the same repo: "
            f"run `amoeba rm` for one of them, then `amoeba add` here again",
        )
    action = OriginAction.RECORD if member.origin is None else OriginAction.REPLACE
    return OriginChange(action, member.origin, origin)
