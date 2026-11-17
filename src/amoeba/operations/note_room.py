"""Room for a note: a sender holds at most ``MAX_NOTES_PER_SENDER`` (slice 243, D6).

Both ways a note is written, ``send`` and ``report-release``, call this inside their
write transaction just before the insert, so ``inbox`` reads at most that many notes
per sender however fast a sender writes.
"""

from __future__ import annotations

from amoeba.operations.message_models import MAX_NOTES_PER_SENDER
from amoeba.store.notes import prune_oldest_notes_from
from amoeba.store.store import Transaction


def make_room_for_note(transaction: Transaction, sender: str) -> None:
    """Drop the sender's oldest notes, with their deliveries, so one more fits.

    A note has no state to wait on, so the oldest always goes; nothing is refused.
    """
    prune_oldest_notes_from(transaction, sender, MAX_NOTES_PER_SENDER - 1)
