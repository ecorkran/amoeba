"""The resume steps' hub side (slice 262, D4, D6).

``claim_resume`` is the one function that takes a resume claim, in one statement, so
every caller (``answer``, ``question_settle``, ``resume_claim``, ``claim_work``) follows
the same rule.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import uuid4

from amoeba.store import sql_local_work
from amoeba.store.answers import get_answer
from amoeba.store.errors import StoreRowError
from amoeba.store.row_values import encode_timestamp
from amoeba.store.store import Transaction
from amoeba.store.vocabulary import ResumeOutcome


@dataclass(frozen=True)
class ResumeClaimed:
    """The caller holds the claim; ``claim_id`` goes with every later write of it."""

    claim_id: str


@dataclass(frozen=True)
class ResumeInFlight:
    """Another attempt holds a claim that has not run out."""


@dataclass(frozen=True)
class ResumeFinal:
    """The answer already has a final outcome (``resumed`` or ``not_delivered``)."""

    outcome: ResumeOutcome


def claim_resume(
    transaction: Transaction, answer_seq: int, now: datetime, limit_seconds: float
) -> ResumeClaimed | ResumeInFlight | ResumeFinal:
    """Take the resume claim for the answer, or say why not.

    Applies only when the outcome is not final and either no claim is held or the held
    one is ``limit_seconds`` old or older.

    Raises:
        StoreRowError: There is no answer with this ``seq``.
    """
    claim_id = uuid4().hex
    cutoff = encode_timestamp(now - timedelta(seconds=limit_seconds))
    cursor = transaction.execute(
        sql_local_work.CLAIM_RESUME,
        (
            encode_timestamp(now),
            claim_id,
            answer_seq,
            ResumeOutcome.REFUSED.value,
            cutoff,
        ),
    )
    if cursor.rowcount == 1:
        return ResumeClaimed(claim_id)
    answer = get_answer(transaction, answer_seq)
    if answer is None:
        raise StoreRowError(f"answer {answer_seq} does not exist to claim")
    outcome = answer.resume_outcome
    if outcome is ResumeOutcome.RESUMED or outcome is ResumeOutcome.NOT_DELIVERED:
        return ResumeFinal(outcome)
    return ResumeInFlight()
