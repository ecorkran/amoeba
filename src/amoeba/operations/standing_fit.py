"""Whether a standing answer leaves every member it reaches under the cap (230 D5).

Run inside ``standing``'s write transaction, after the row is inserted, so the new
row is counted with the active rows already reaching each member. Only the standing
answers' share is checked: the rules, plan and program text they join changes with
each question, so ``assemble`` checks the whole at every pause and a set that no
longer fits waits as ``sources_too_large``.
"""

from __future__ import annotations

from amoeba.answering.passages import standing_chars
from amoeba.operations.standing_sources import standing_answers_of
from amoeba.store.models import Member
from amoeba.store.programs import get_member, list_programs, members_of
from amoeba.store.standing import standing_reaching
from amoeba.store.store import Transaction
from amoeba.store.vocabulary import StandingReach


def overflow(
    transaction: Transaction,
    reach: StandingReach,
    program_id: str | None,
    member_id: str | None,
    max_chars: int,
) -> str | None:
    """A problem line naming the first reached member whose standing answers render
    past ``max_chars``; ``None`` when every one fits."""
    for member in _reached(transaction, reach, program_id, member_id):
        rows = standing_reaching(transaction, member.project_id, member.program_id)
        size = standing_chars(standing_answers_of(rows))
        if size > max_chars:
            return (
                f"the standing answers reaching {member.project_id} would be {size} "
                f"characters; passages_max_chars is {max_chars}, so no answering run "
                "there could be sent them"
            )
    return None


def _reached(
    transaction: Transaction,
    reach: StandingReach,
    program_id: str | None,
    member_id: str | None,
) -> tuple[Member, ...]:
    """The active members a row of this reach reaches now."""
    match reach:
        case StandingReach.ALL:
            return tuple(
                member
                for program in list_programs(transaction)
                for member in members_of(transaction, program.program_id)
            )
        case StandingReach.PROGRAM:
            if program_id is None:
                raise ValueError("reach program needs a program id")
            return members_of(transaction, program_id)
        case StandingReach.MEMBER:
            if member_id is None:
                raise ValueError("reach member needs a member id")
            found = get_member(transaction, member_id)
            return () if found is None else (found,)
