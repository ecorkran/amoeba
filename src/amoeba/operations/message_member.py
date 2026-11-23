"""Who sends, replies or cancels, and who a request is addressed to (slice 240, D3;
slice 261, D6).

The caller is the member whose checkout is the acting machine's and the project id
the client part gathered (``operations.here``); a named member is read from the store
by name or id. No lookup here calls ``cf``. A refusal is a returned value, never an
exception.
"""

from __future__ import annotations

from dataclasses import dataclass

from amoeba.operations.caller import NotAProject, NotInProgram, find_caller, find_member
from amoeba.operations.here_document import HereCaller, HereNotAProject
from amoeba.operations.reject_codes import RejectCode
from amoeba.operations.release_member import not_a_member_detail
from amoeba.store.machines import acting_machine_id
from amoeba.store.store import Store, Transaction

__all__ = [
    "Caller",
    "Recipient",
    "Refusal",
    "UnknownActor",
    "resolve_actor",
    "resolve_caller",
    "actor_of",
    "caller_of",
    "recipient_of",
    "resolve_recipient",
]


@dataclass(frozen=True)
class Caller:
    """The active member the call is made by."""

    member_id: str


@dataclass(frozen=True)
class Recipient:
    """The active member a request is addressed to."""

    member_id: str


@dataclass(frozen=True)
class UnknownActor:
    """No member made the call (``cancel`` from a directory in no member): nobody is
    left out of the deliveries."""


@dataclass(frozen=True)
class Refusal:
    """A lookup that ends the call as ``rejected``."""

    code: RejectCode
    detail: str
    #: The member a ``message_rejections`` row goes under (D9); ``None`` when there is
    #: no member to show it under.
    record_under: str | None


def resolve_caller(
    transaction: Transaction,
    machine_id: int,
    here: HereCaller | HereNotAProject,
    member: str | None,
) -> Caller | Refusal:
    """The caller: the member whose checkout is here, else the explicit ``member``.

    An explicit ``member`` naming a different member than the checkout's is
    ``member_mismatch``, recorded under the checkout's member. A project with no
    checkout takes the explicit ``member`` (which must be an active member); with
    none, the caller is ``not_a_member``.
    """
    resolved = find_caller(transaction, machine_id, here)
    named = None if member is None else find_member(transaction, member)
    if not isinstance(resolved, NotInProgram | NotAProject):
        if member is not None and (
            named is None or named.project_id != resolved.project_id
        ):
            return Refusal(
                RejectCode.MEMBER_MISMATCH,
                f"member {member!r} is not the member this directory belongs to",
                record_under=resolved.project_id,
            )
        return Caller(resolved.project_id)
    if named is not None:
        return Caller(named.project_id)
    detail = (
        not_a_member_detail(resolved)
        if member is None
        else f"member {member!r} is no active member of any program"
    )
    return Refusal(RejectCode.NOT_A_MEMBER, detail, record_under=None)


def resolve_actor(
    transaction: Transaction,
    machine_id: int,
    here: HereCaller | HereNotAProject,
    member: str | None,
) -> Caller | UnknownActor | Refusal:
    """As ``resolve_caller``, but a call that names no member and comes from a
    project in none is an ``UnknownActor``, not a refusal (``cancel`` checks nothing
    about who calls, D3). An explicit ``member`` that is no active member, and a
    mismatch, are still refusals: the caller said who it is, and that is wrong.
    """
    caller = resolve_caller(transaction, machine_id, here, member)
    if (
        member is None
        and isinstance(caller, Refusal)
        and caller.code is RejectCode.NOT_A_MEMBER
    ):
        return UnknownActor()
    return caller


def resolve_recipient(transaction: Transaction, reference: str) -> Recipient | Refusal:
    """The active member ``reference`` names, by name or id, in any program."""
    member = find_member(transaction, reference)
    if member is None:
        return Refusal(
            RejectCode.UNKNOWN_RECIPIENT,
            f"{reference!r} is not an active member of any program",
            record_under=None,
        )
    return Recipient(member.project_id)


def caller_of(
    store: Store, here: HereCaller | HereNotAProject, member: str | None
) -> Caller | Refusal:
    """``resolve_caller`` in its own read transaction on the acting machine."""
    with store.read() as transaction:
        return resolve_caller(transaction, acting_machine_id(transaction), here, member)


def actor_of(
    store: Store, here: HereCaller | HereNotAProject, member: str | None
) -> Caller | UnknownActor | Refusal:
    """``resolve_actor`` in its own read transaction on the acting machine."""
    with store.read() as transaction:
        return resolve_actor(transaction, acting_machine_id(transaction), here, member)


def recipient_of(store: Store, reference: str) -> Recipient | Refusal:
    """``resolve_recipient`` in its own read transaction on the acting machine."""
    with store.read() as transaction:
        return resolve_recipient(transaction, reference)
