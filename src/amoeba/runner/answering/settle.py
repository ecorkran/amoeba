"""``settle_pending``: what a pending question's turn in the tick comes to (D5).

Pure: no store, no I/O. The caller reads the record and its block and applies the
result. The last branch is the launch of an answering run (slice 144, D14).
"""

from __future__ import annotations

from dataclasses import dataclass

from amoeba.store import BlockedState, DeclineReason, QuestionRecord


class QuestionInvariantError(RuntimeError):
    """A pending question is in a state the store's own writes cannot produce."""


@dataclass(frozen=True)
class Skip:
    """Leave the record alone: the PM's resolution settles it at acknowledgment."""


@dataclass(frozen=True)
class Decline:
    """Decline the record for ``reason``."""

    reason: DeclineReason


@dataclass(frozen=True)
class Launch:
    """Nothing declines the record: an answering run should be launched for it."""


def settle_pending(
    record: QuestionRecord, block: BlockedState, *, configured: bool
) -> Skip | Decline | Launch:
    """Settle one pending record, checking block state first.

    A question the PM is already answering is skipped, not declined and announced.
    A resolved block that awaits no acknowledgment cannot happen (an applied resume
    answers the record in the acknowledgment's own transaction, and a stop or a
    rejection moves it to the new open block), so it raises instead of hiding behind
    a decline reason that later slices would inherit.

    Raises:
        QuestionInvariantError: The block is resolved and not awaiting the Runner.
    """
    if block.is_resolved:
        if block.awaits_runner:
            return Skip()
        raise QuestionInvariantError(
            f"question {record.id!r}: block {block.id!r} is resolved and no "
            "resolution awaits the Runner"
        )
    if not record.question:
        return Decline(DeclineReason.QUESTION_MISSING)
    if not configured:
        return Decline(DeclineReason.ANSWERER_NOT_CONFIGURED)
    return Launch()
