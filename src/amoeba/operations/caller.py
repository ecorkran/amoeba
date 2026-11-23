"""Who is calling, and who is named (slice 261, D6).

Neither lookup calls ``cf``: the caller is found by the Context Forge project id the
client part gathered (``operations.here``) and the machine the call came from, and a
named member by its name or id in the store. This module imports nothing from
``upstream``, so the hub can use it.
"""

from __future__ import annotations

from dataclasses import dataclass

from amoeba.operations.here_document import Here, HereNotAProject
from amoeba.store.checkouts import checkout_at
from amoeba.store.member_names import active_member_by_name
from amoeba.store.models import Member
from amoeba.store.programs import get_member, get_member_any
from amoeba.store.store import Transaction


@dataclass(frozen=True)
class NotInProgram:
    """A Context Forge project that is not a member of any program."""

    cf_id: str


@dataclass(frozen=True)
class NotAProject:
    """A directory outside every Context Forge project; ``message`` is CF's text."""

    message: str


def acting_machine_id(transaction: Transaction) -> int:
    """The machine this call acts as: the token's on a hub, ``local`` otherwise."""
    return transaction.acting("checkouts").machine_id


def find_caller(
    transaction: Transaction, machine_id: int, here: Here
) -> Member | NotInProgram | NotAProject:
    """The active member whose checkout is (``machine_id``, the gathered project id).

    The same project id on another machine is another checkout, so it is
    ``NotInProgram`` here. A removed member's checkouts are deleted with it, and one
    left behind is not on record.
    """
    if isinstance(here, HereNotAProject):
        return NotAProject(here.not_a_project)
    checkout = checkout_at(transaction, machine_id, here.project_id)
    if checkout is None:
        return NotInProgram(here.project_id)
    member = get_member(transaction, checkout.member_id)
    return NotInProgram(here.project_id) if member is None else member


def find_member(transaction: Transaction, reference: str) -> Member | None:
    """The active member whose name is ``reference`` in any case, else whose id is.

    No name equals another member's id (D1), so a reference never means two members.
    """
    named = active_member_by_name(transaction, reference)
    return get_member(transaction, reference) if named is None else named


def find_member_for_removal(transaction: Transaction, reference: str) -> Member | None:
    """As :func:`find_member`, then a removed member by its id only (D6, D8).

    A removed member's name is free and may be another member's by now, so only its
    id says which removed member is meant: ``rm <id>`` twice is ``unchanged``.
    """
    found = find_member(transaction, reference)
    if found is not None:
        return found
    removed = get_member_any(transaction, reference)
    return removed if removed is not None and removed.removed_at is not None else None
