"""Name checks for ``add`` (slice 261, D1, D7): one "free or taken" rule.

A name is taken when an active member has it, or it equals any other member's id, in
any case. Read-only.
"""

from __future__ import annotations

from typing import Final

from amoeba.operations.set_up_models import SetUpProblem, SetUpProblemCode
from amoeba.store.member_names import active_member_by_name, name_is_other_members_id
from amoeba.store.models import Member
from amoeba.store.store import Transaction
from amoeba.store.vocabulary import MEMBER_NAME_MAX_LENGTH, is_member_name

NAME_RULE: Final = (
    f"a name starts with a letter or digit, then letters, digits, '.', '_' or '-', "
    f"at most {MEMBER_NAME_MAX_LENGTH} characters"
)


def refusal(code: SetUpProblemCode, detail: str) -> SetUpProblem:
    return SetUpProblem(code=code, detail=detail)


def name_holder(
    transaction: Transaction, name: str, member_id: str | None
) -> Member | None:
    """The active member that has ``name``, other than ``member_id`` itself."""
    holder = active_member_by_name(transaction, name)
    if holder is not None and holder.project_id != member_id:
        return holder
    return None


def name_is_taken(transaction: Transaction, name: str, member_id: str | None) -> bool:
    """Whether ``name`` is taken for ``member_id``: another active member has it, or it
    equals another member's id (D1)."""
    return name_holder(transaction, name, member_id) is not None or (
        name_is_other_members_id(transaction, name, member_id or "")
    )


def check_given_name(
    transaction: Transaction, name: str, member_id: str | None
) -> SetUpProblem | None:
    if not is_member_name(name):
        return refusal(
            SetUpProblemCode.MALFORMED,
            f"name {name!r} is not a member name: {NAME_RULE}",
        )
    if name_is_taken(transaction, name, member_id):
        return refusal(
            SetUpProblemCode.NAME_TAKEN,
            f"name {name!r} is another member's name or id; give another --name",
        )
    return None
