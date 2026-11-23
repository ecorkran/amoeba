"""Which member a checkout belongs to (slice 261, D7): the five steps of ``add``.

``plan_member`` only reads. It decides the member (an existing one, a removed one
registered again, or a new one), its name, the checkout to attach and any change to
the member's ``origin``, and returns that as a ``MemberPlan`` for the engine to write
in the same transaction, or the problem that refuses the call. A refusal writes
nothing because nothing was written yet.

"Free" and "taken" are one check (D1): a name is taken when an active member has it,
or it equals another member's id, in any case.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final
from uuid import uuid4

from amoeba.operations.add_names import (
    NAME_RULE,
    check_given_name,
    name_is_taken,
    refusal,
)
from amoeba.operations.add_origin import OriginAction, OriginChange, origin_change
from amoeba.operations.caller import find_member
from amoeba.operations.here_document import HereCheckout
from amoeba.operations.set_up_models import SetUpProblem, SetUpProblemCode
from amoeba.store.checkouts import checkout_at, checkouts_of_member
from amoeba.store.machines import acting_machine_id
from amoeba.store.member_names import (
    active_member_by_origin,
    removed_member_by_origin,
)
from amoeba.store.models import Member
from amoeba.store.programs import get_member_any
from amoeba.store.store import Transaction
from amoeba.store.vocabulary import is_member_name

NONE_RECORDED: Final = "none recorded"


@dataclass(frozen=True)
class MemberPlan:
    """What ``add`` does for the entry that names no member."""

    member_id: str
    #: The member's name after the call.
    name: str
    #: The stored name when it changes (``--name``), else ``None``.
    renamed_from: str | None
    #: A member row to create, with this id and ``name``.
    is_new: bool
    #: A removed member to register again.
    reregister: bool
    #: The program a new or re-registered member joins: ``--program``, the removed
    #: member's, or a new one named for the member. ``None`` for an existing member,
    #: which stays in its own.
    program_id: str | None
    #: The checkout to insert for this call's directory; ``None`` when it is on record.
    attach: HereCheckout | None
    #: A checkout left by a removed member, deleted before the attach.
    stale_checkout_id: int | None
    origin: OriginChange | None


def _existing(
    member: Member,
    here: HereCheckout,
    *,
    attach: bool,
    stale: int | None,
    origin: OriginChange | None,
    new_name: str | None,
) -> MemberPlan:
    return MemberPlan(
        member_id=member.project_id,
        name=member.name if new_name is None else new_name,
        renamed_from=None if new_name in (None, member.name) else member.name,
        is_new=False,
        reregister=False,
        program_id=None,
        attach=here if attach else None,
        stale_checkout_id=stale,
        origin=origin,
    )


def plan_member(  # noqa: PLR0913 - the flags of one call
    transaction: Transaction,
    here: HereCheckout,
    *,
    name: str | None,
    attach_to: str | None,
    new_member: bool,
    program: str | None,
) -> MemberPlan | SetUpProblem:
    """The member for the checkout ``here``, by D7's steps, or the refusal."""
    machine_id = acting_machine_id(transaction)
    on_record = checkout_at(transaction, machine_id, here.project_id)
    stale: int | None = None
    if on_record is not None:
        owner = get_member_any(transaction, on_record.member_id)
        if owner is not None and owner.removed_at is None:
            return _on_record(transaction, owner, here, name, attach_to, new_member)
        stale = on_record.checkout_id
    if attach_to is not None:
        return _attach_to(transaction, here, attach_to, name, stale)
    if not new_member and here.origin is not None:
        found = _by_origin(transaction, here, name, program, stale)
        if found is not None:
            return found
    return _create(transaction, here, name, new_member, program, stale)


def _on_record(
    transaction: Transaction,
    member: Member,
    here: HereCheckout,
    name: str | None,
    attach_to: str | None,
    new_member: bool,
) -> MemberPlan | SetUpProblem:
    """Step 1: this checkout is on record, so it is its member's; the stored path is
    kept, whatever path arrived."""
    if attach_to is not None or new_member:
        flag = "--attach-to" if attach_to is not None else "--new-member"
        return refusal(
            SetUpProblemCode.MALFORMED,
            f"{flag}: this checkout is already on record for member {member.name!r}; "
            "run `amoeba rm --checkout <path>` first",
        )
    if name is not None:
        problem = check_given_name(transaction, name, member.project_id)
        if problem is not None:
            return problem
    change = origin_change(transaction, member, here.origin, strict=False)
    if isinstance(change, SetUpProblem):
        return change
    return _existing(
        member, here, attach=False, stale=None, origin=change, new_name=name
    )


def _attach_to(
    transaction: Transaction,
    here: HereCheckout,
    reference: str,
    name: str | None,
    stale: int | None,
) -> MemberPlan | SetUpProblem:
    """``--attach-to``: that member, when it has no checkout on any machine."""
    member = find_member(transaction, reference)
    if member is None:
        return refusal(
            SetUpProblemCode.NOT_A_MEMBER, f"--attach-to: no member named {reference!r}"
        )
    if checkouts_of_member(transaction, member.project_id):
        return refusal(
            SetUpProblemCode.MEMBER_HAS_CHECKOUTS,
            f"member {member.name!r} already has a checkout, so its origin decides "
            "which repo a new one belongs to: run `amoeba add` with the same origin "
            "remote, or `--new-member`",
        )
    if name is not None:
        problem = check_given_name(transaction, name, member.project_id)
        if problem is not None:
            return problem
    change = origin_change(transaction, member, here.origin, strict=True)
    if isinstance(change, SetUpProblem):
        return change
    return _existing(
        member, here, attach=True, stale=stale, origin=change, new_name=name
    )


def _by_origin(
    transaction: Transaction,
    here: HereCheckout,
    name: str | None,
    program: str | None,
    stale: int | None,
) -> MemberPlan | SetUpProblem | None:
    """Steps 2 and 3: the member that has this ``origin``, active or removed."""
    if here.origin is None:
        return None
    active = active_member_by_origin(transaction, here.origin)
    if active is not None:
        if name is not None:
            problem = check_given_name(transaction, name, active.project_id)
            if problem is not None:
                return problem
        return _existing(
            active, here, attach=True, stale=stale, origin=None, new_name=name
        )
    removed = removed_member_by_origin(transaction, here.origin)
    if removed is None:
        return None
    wanted = removed.name if name is None else name
    if name is None and name_is_taken(transaction, wanted, removed.project_id):
        return refusal(
            SetUpProblemCode.NAME_TAKEN,
            f"the removed member {removed.name!r} of this repo would come back, but "
            "its name is taken now; give another --name",
        )
    if name is not None:
        problem = check_given_name(transaction, name, removed.project_id)
        if problem is not None:
            return problem
    return MemberPlan(
        member_id=removed.project_id,
        name=wanted,
        renamed_from=None if wanted == removed.name else removed.name,
        is_new=False,
        reregister=True,
        program_id=removed.program_id if program is None else program,
        attach=here,
        stale_checkout_id=stale,
        origin=None,
    )


def _create(  # noqa: PLR0913 - steps 4 and 5 and the flags
    transaction: Transaction,
    here: HereCheckout,
    name: str | None,
    new_member: bool,
    program: str | None,
    stale: int | None,
) -> MemberPlan | SetUpProblem:
    """Step 4: a free name makes a new member. Step 5: a taken one is refused."""
    chosen = here.name if name is None else name
    if name is not None:
        problem = check_given_name(transaction, chosen, None)
        if problem is not None:
            return problem
    elif not is_member_name(chosen):
        return refusal(
            SetUpProblemCode.MALFORMED,
            f"the Context Forge name {chosen!r} is not a member name ({NAME_RULE}); "
            "give --name",
        )
    else:
        taken = name_is_taken(transaction, chosen, None)
        if isinstance(taken, Member):
            has_checkout = bool(checkouts_of_member(transaction, taken.project_id))
            return _name_taken(taken, here, new_member, has_checkout)
        if taken:
            return refusal(
                SetUpProblemCode.NAME_TAKEN,
                f"the name {chosen!r} is another member's id; give --name",
            )
    origin = here.origin
    if origin is not None and active_member_by_origin(transaction, origin) is not None:
        origin = None  # --new-member: the other member keeps it; this one has none
    return MemberPlan(
        member_id=uuid4().hex,
        name=chosen,
        renamed_from=None,
        is_new=True,
        reregister=False,
        program_id=chosen if program is None else program,
        attach=here,
        stale_checkout_id=stale,
        origin=None
        if origin is None
        else OriginChange(OriginAction.RECORD, None, origin),
    )


def _name_taken(
    holder: Member, here: HereCheckout, new_member: bool, has_checkout: bool
) -> SetUpProblem:
    """Step 5: an active member has the name."""
    if new_member:
        return refusal(
            SetUpProblemCode.NAME_TAKEN,
            f"--new-member: the name {holder.name!r} is taken; give another --name",
        )
    if here.origin is None:
        return refusal(
            SetUpProblemCode.NO_ORIGIN,
            f"member {holder.name!r} has this name, and this checkout has no origin "
            "remote, so nothing shows it is the same repo; a repo with no origin can "
            "have one checkout. Add an origin remote to this repo, or give --name for "
            "a separate member",
        )
    return refusal(
        SetUpProblemCode.NAME_TAKEN,
        f"member {holder.name!r} has this name; its origin is "
        f"{holder.origin or NONE_RECORDED} and this checkout's is {here.origin}. For "
        f"a different repo give --name. {_same_repo_way(holder, has_checkout)}",
    )


def _same_repo_way(holder: Member, has_checkout: bool) -> str:
    """The way on when it is the same repo (D7 step 5)."""
    if holder.origin is not None:
        return "For the same repo: the origins differ, so add the right origin remote"
    if has_checkout:
        return (
            "For the same repo: give the member's checkout this origin remote and "
            "run `amoeba add` there so the origin is recorded, then `amoeba add` here"
        )
    return f"For the same repo: `amoeba add --attach-to {holder.name}` here"
