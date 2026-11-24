"""``pause_sources``: what the gather reads from the store (262 D4, D5).

The program, its members, the PM precedent, the standing answers, and the concept
member's checkout on the calling machine (its path and Context Forge id only: a wake
command is returned by ``wake_read`` alone). A named request's result is read here too.
"""

from __future__ import annotations

from amoeba.operations.steps.context import StepContext
from amoeba.operations.steps.models_pause import (
    CheckoutRef,
    PauseSourcesReply,
    PauseSourcesRequest,
)
from amoeba.operations.steps.pause import request_facts
from amoeba.store.answers import pm_precedent
from amoeba.store.checkouts import first_checkout_on
from amoeba.store.errors import StoreRowError
from amoeba.store.machines import acting_machine_id
from amoeba.store.programs import get_member, get_program, members_of
from amoeba.store.standing import standing_reaching


def pause_sources(
    context: StepContext, request: PauseSourcesRequest
) -> PauseSourcesReply:
    """The stored facts a gather needs for ``request.member_id``'s pause.

    Raises:
        StoreRowError: The member or its program is not stored.
    """
    transaction = context.transaction
    member = get_member(transaction, request.member_id)
    if member is None:
        raise StoreRowError(f"member {request.member_id} is not stored")
    program = get_program(transaction, member.program_id)
    if program is None:
        raise StoreRowError(f"member {member.project_id} has no program record")
    concept = None
    if program.concept_member is not None:
        row = first_checkout_on(
            transaction, program.concept_member, acting_machine_id(transaction)
        )
        if row is not None:
            concept = CheckoutRef(path=row.path, cf_project_id=row.cf_project_id)
    facts = (
        None
        if request.request_id is None
        else request_facts(transaction, request.request_id, context.now)
    )
    return PauseSourcesReply(
        program=program,
        members=members_of(transaction, member.program_id),
        precedent=pm_precedent(transaction, member.project_id),
        standing=standing_reaching(transaction, member.project_id, member.program_id),
        concept_checkout=concept,
        request=facts,
    )
