"""Who sends, replies or cancels, and who a request is addressed to (slice 240, D3).

Every lookup goes through ``cf`` before the store is locked. A refusal is a returned
value, never an exception; a ``cf`` failure or timeout is not a refusal and propagates
as ``ContextForgeError`` (the CLI exits 3, nothing is written).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from amoeba.operations.caller import NotAProject, NotInProgram
from amoeba.operations.member_reference import anchor
from amoeba.operations.members import resolve_member
from amoeba.operations.reject_codes import RejectCode
from amoeba.operations.release_member import not_a_member_detail
from amoeba.store.programs import get_member
from amoeba.store.store import Store
from amoeba.upstream.context_forge.cli_call import CfRun

__all__ = [
    "Caller",
    "Recipient",
    "Refusal",
    "UnknownActor",
    "resolve_actor",
    "resolve_caller",
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
    #: Context Forge's ``projectPath``, the checkout a wake runs in (244 D4); ``None``
    #: when ``cf`` did not know the reference, which is then read as an id.
    project_path: str | None
    #: The member's wake command as read now; ``None`` means no wake step (244 D2).
    wake_command: str | None


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


def _is_active_member(store: Store, project_id: str) -> bool:
    with store.read() as transaction:
        return get_member(transaction, project_id) is not None


def resolve_caller(
    store: Store, directory: Path, member: str | None, run: CfRun
) -> Caller | Refusal:
    """The caller: the member ``directory`` is in, else the explicit ``member``.

    The directory is always looked up. An explicit ``member`` naming a different member
    than the directory's is ``member_mismatch``, recorded under the directory's member.
    A directory in no member takes the explicit ``member`` (which must be an active
    member); with none, the caller is ``not_a_member``.

    Raises:
        ContextForgeError: ``cf`` failed or timed out; nothing should be written.
    """
    resolved = resolve_member(store, directory, run)
    named = None if member is None else anchor(member, run)
    if not isinstance(resolved, NotInProgram | NotAProject):
        if named is not None and named.project_id != resolved.project_id:
            return Refusal(
                RejectCode.MEMBER_MISMATCH,
                f"member {named.text!r} is not the member this directory belongs to",
                record_under=resolved.project_id,
            )
        return Caller(resolved.project_id)
    if named is not None and _is_active_member(store, named.project_id):
        return Caller(named.project_id)
    detail = (
        not_a_member_detail(resolved)
        if named is None
        else f"member {named.text!r} is no active member of any program"
    )
    return Refusal(RejectCode.NOT_A_MEMBER, detail, record_under=None)


def resolve_actor(
    store: Store, directory: Path, member: str | None, run: CfRun
) -> Caller | UnknownActor | Refusal:
    """As ``resolve_caller``, but a call that names no member and comes from a
    directory in none is an ``UnknownActor``, not a refusal (``cancel`` checks nothing
    about who calls, D3). An explicit ``member`` that is no active member, and a
    mismatch, are still refusals: the caller said who it is, and that is wrong.

    Raises:
        ContextForgeError: ``cf`` failed or timed out; nothing should be written.
    """
    caller = resolve_caller(store, directory, member, run)
    if (
        member is None
        and isinstance(caller, Refusal)
        and caller.code is RejectCode.NOT_A_MEMBER
    ):
        return UnknownActor()
    return caller


def resolve_recipient(store: Store, reference: str, run: CfRun) -> Recipient | Refusal:
    """The active member ``reference`` names, in any program, with its checkout path
    and wake command. One member read serves all three, so waking adds no read.

    Raises:
        ContextForgeError: ``cf`` failed or timed out; nothing should be written.
    """
    found = anchor(reference, run)
    with store.read() as transaction:
        member = get_member(transaction, found.project_id)
    if member is not None:
        return Recipient(
            found.project_id, found.project_path, member.settings.wake_command
        )
    return Refusal(
        RejectCode.UNKNOWN_RECIPIENT,
        f"{reference!r} is not an active member of any program",
        record_under=None,
    )
