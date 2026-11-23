"""Writing what ``add_member`` planned for the entry that names no member (261 D7).

Runs inside the engine's write transaction, after the checks passed: the member row's
name, the stale checkout it replaces, the checkout this call attaches, and a change
to the member's ``origin``. Each makes one change record, in the words of ``add``'s
result.
"""

from __future__ import annotations

from datetime import datetime

from amoeba.operations.add_member import MemberPlan, OriginAction
from amoeba.operations.here_document import HereCheckout
from amoeba.operations.set_up_models import Change, ChangeSubject, ChangeVerb
from amoeba.store.checkouts import delete_checkout, insert_checkout
from amoeba.store.member_names import set_member_name, set_member_origin
from amoeba.store.store import Transaction


def name_before_write(
    transaction: Transaction, plan: MemberPlan, now: datetime
) -> None:
    """A removed member registered again takes its planned name first, so the unique
    index on active names never sees the old one."""
    if plan.reregister and plan.renamed_from is not None:
        set_member_name(transaction, plan.member_id, plan.name, now)


def apply_plan(
    transaction: Transaction, plan: MemberPlan, here: HereCheckout, now: datetime
) -> list[Change]:
    """The writes after the member row exists, with their change records."""
    changes: list[Change] = []
    if plan.renamed_from is not None and not plan.reregister:
        set_member_name(transaction, plan.member_id, plan.name, now)
        changes.append(_member_change(f"{plan.renamed_from} is now named {plan.name}"))
    if plan.stale_checkout_id is not None:
        delete_checkout(transaction, plan.stale_checkout_id)
    if plan.attach is not None:
        insert_checkout(
            transaction,
            member_id=plan.member_id,
            cf_project_id=here.project_id,
            path=here.path,
            wake_command=None,
            now=now,
        )
        changes.append(
            Change(
                verb=ChangeVerb.ADDED,
                subject=ChangeSubject.CHECKOUT,
                detail=f"{here.path} of {plan.name}",
            )
        )
    if plan.origin is not None:
        set_member_origin(transaction, plan.member_id, plan.origin.new, now)
        changes.append(_member_change(_origin_text(plan)))
    return changes


def _origin_text(plan: MemberPlan) -> str:
    change = plan.origin
    if change is None:
        raise ValueError("a plan with no origin change has no origin text")
    if change.action is OriginAction.RECORD:
        return f"{plan.name} origin {change.new}"
    return f"{plan.name} origin {change.old} -> {change.new}"


def _member_change(detail: str) -> Change:
    return Change(verb=ChangeVerb.UPDATED, subject=ChangeSubject.MEMBER, detail=detail)
