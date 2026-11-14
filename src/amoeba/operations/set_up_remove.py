"""``set_up`` removal, steps 3 and 4: the checks and the writes (228 D8).

Both run inside ``set_up``'s one write transaction, so the open-question check and the
removal see the same state. A reference with no member row at all (in any program) is
``not_a_member``; an already removed member or an absent pair is no change.
"""

from __future__ import annotations

from datetime import datetime

from amoeba.operations.set_up_models import (
    Change,
    ChangeSubject,
    ChangeVerb,
    OpenQuestion,
    SetUpProblem,
    SetUpProblemCode,
)
from amoeba.operations.set_up_remove_resolve import (
    Reference,
    RemovedMember,
    RemovedPair,
    ResolvedRemoval,
)
from amoeba.store.models import Member
from amoeba.store.programs import (
    get_member_any,
    get_program,
    remove_member,
    remove_pair,
)
from amoeba.store.question_closing import member_open_questions
from amoeba.store.store import Transaction


def _problem(code: SetUpProblemCode, detail: str) -> SetUpProblem:
    return SetUpProblem(code=code, detail=detail)


def _member_of_program(
    transaction: Transaction, program_id: str, reference: Reference
) -> Member | None:
    """The member row, removed or not, when it belongs to this program."""
    member = get_member_any(transaction, reference.project_id)
    if member is None or member.program_id != program_id:
        return None
    return member


def _not_a_member(path: str, program_id: str, reference: Reference) -> SetUpProblem:
    detail = (
        f"{path}: {reference.text!r} ({reference.project_id}) is not and was never "
        f"a member of program {program_id!r}"
    )
    if not reference.known_to_cf:
        detail += "; Context Forge has no such project, so it was read as a member id"
    return _problem(SetUpProblemCode.NOT_A_MEMBER, detail)


def _removed_member_problems(
    transaction: Transaction, program_id: str, item: RemovedMember
) -> list[SetUpProblem]:
    path = f"remove.members.{item.index}"
    member = _member_of_program(transaction, program_id, item.reference)
    if member is None:
        return [_not_a_member(path, program_id, item.reference)]
    if member.removed_at is not None:
        return []
    open_rows = member_open_questions(transaction, member.project_id)
    if not open_rows:
        return []
    keys = ", ".join(f"{row.key.run_id} at {row.key.paused_at}" for row in open_rows)
    return [
        SetUpProblem(
            code=SetUpProblemCode.MEMBER_HAS_OPEN_QUESTIONS,
            detail=f"{path}: {item.reference.text!r} has open questions ({keys}); "
            "`dismiss` or `answer` them first",
            open_questions=tuple(
                OpenQuestion(run_id=row.key.run_id, paused_at=row.key.paused_at)
                for row in open_rows
            ),
        )
    ]


def _removed_pair_problems(
    transaction: Transaction, program_id: str, item: RemovedPair
) -> list[SetUpProblem]:
    return [
        _not_a_member(f"remove.pairs.{item.index}.{end}", program_id, reference)
        for end, reference in (("provider", item.provider), ("consumer", item.consumer))
        if _member_of_program(transaction, program_id, reference) is None
    ]


def _concept_problems(
    transaction: Transaction, program_id: str, removal: ResolvedRemoval
) -> list[SetUpProblem]:
    """The stored concept's member may not be removed while the concept stays."""
    program = get_program(transaction, program_id)
    if program is None or program.concept_member is None:
        return []
    return [
        _problem(
            SetUpProblemCode.CONCEPT_MEMBER_NOT_MEMBER,
            f"remove.members.{item.index}: {item.reference.text!r} "
            f"({item.reference.project_id}) is the concept member of program "
            f"{program_id!r}; clear the concept (concept: null) or move it in the "
            "same request",
        )
        for item in removal.members
        if item.reference.project_id == program.concept_member
    ]


def check_removal(
    transaction: Transaction,
    program_id: str,
    removal: ResolvedRemoval,
    *,
    concept_given: bool,
) -> list[SetUpProblem]:
    """Every problem the removal has against the stored state.

    ``concept_given``: the request sets or clears the concept, so the concept member
    is checked by the request's own concept check (or is gone with ``concept: null``).
    """
    problems: list[SetUpProblem] = []
    for item in removal.members:
        problems += _removed_member_problems(transaction, program_id, item)
    for pair in removal.pairs:
        problems += _removed_pair_problems(transaction, program_id, pair)
    if not concept_given:
        problems += _concept_problems(transaction, program_id, removal)
    return problems


def apply_removal(
    transaction: Transaction, removal: ResolvedRemoval, now: datetime
) -> list[Change]:
    """Remove what is still there; one change record per removal made."""
    changes: list[Change] = []
    for pair in removal.pairs:
        provider, consumer = pair.provider.project_id, pair.consumer.project_id
        if remove_pair(transaction, provider, consumer):
            changes.append(
                Change(
                    verb=ChangeVerb.REMOVED,
                    subject=ChangeSubject.PAIR,
                    detail=f"{provider} -> {consumer}",
                )
            )
    for item in removal.members:
        if remove_member(transaction, item.reference.project_id, now):
            changes.append(
                Change(
                    verb=ChangeVerb.REMOVED,
                    subject=ChangeSubject.MEMBER,
                    detail=item.reference.project_id,
                )
            )
    return changes
