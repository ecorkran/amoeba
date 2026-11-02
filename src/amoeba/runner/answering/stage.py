"""The answering stage: settle every pending question, store only (D5).

Reads the project's pending records and applies ``settle_pending`` to each. It
starts no subprocess, so it takes no budget. 144 grows it with the launch.
"""

from __future__ import annotations

from amoeba.runner.answering.settle import (
    Decline,
    QuestionInvariantError,
    settle_pending,
)
from amoeba.store import Store


def settle_pending_questions(
    store: Store, project_id: str, *, configured: bool
) -> bool:
    """Decline what cannot be answered; return whether anything was written.

    Raises:
        QuestionInvariantError: A pending record has no block, or its block breaks
            the invariant ``settle_pending`` names.
    """
    wrote = False
    for record in store.pending_questions(project_id):
        block = (
            None
            if record.blocked_state_id is None
            else store.blocked_state(record.blocked_state_id)
        )
        if block is None:
            raise QuestionInvariantError(
                f"pending question {record.id!r} is linked to no block"
            )
        settled = settle_pending(record, block, configured=configured)
        if isinstance(settled, Decline):
            store.decline_question(record.id, reason=settled.reason)
            wrote = True
    return wrote
