"""What a machine has waiting, read from records (slice 262, D10).

Four kinds: a resume (an answered question's latest answer with no outcome that
``claim_resume`` would take), a ``handle-pause`` for a held question whose request has
ended, one for a claim that has gone stale, and a wake for a member with a wakeable
checkout on the machine. Every function takes the machine whose files the work needs;
a row with no machine is never work. Times are the caller's: the hub's clock.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from amoeba.store import sql_local_work
from amoeba.store.models import QuestionRecord
from amoeba.store.question_rows import question_from_row
from amoeba.store.row_values import encode_timestamp, integer, text
from amoeba.store.store import Transaction
from amoeba.store.vocabulary import QuestionState, RequestState


@dataclass(frozen=True)
class ResumeWork:
    """An answer waiting for its machine to resume the run."""

    answer_seq: int
    run_id: str
    #: How many resumes ``claim_work`` has already handed out for it.
    start_count: int


def _cutoff(now: datetime, seconds: float) -> str:
    return encode_timestamp(now - timedelta(seconds=seconds))


def resume_work(
    transaction: Transaction, machine_id: int, now: datetime, claim_seconds: float
) -> tuple[ResumeWork, ...]:
    """The answers on ``machine_id`` that ``claim_resume`` would take now, oldest
    first: no outcome, and no claim or a claim ``claim_seconds`` old or older."""
    rows = transaction.execute(
        sql_local_work.SELECT_RESUME_WORK,
        (machine_id, QuestionState.ANSWERED.value, _cutoff(now, claim_seconds)),
    ).fetchall()
    return tuple(
        ResumeWork(
            answer_seq=integer(row[0], "answers.seq"),
            run_id=text(row[1], "answers.run_id"),
            start_count=integer(row[2], "answers.resume_start_count"),
        )
        for row in rows
    )


def held_work(
    transaction: Transaction, machine_id: int, now: datetime, wait_seconds: float
) -> tuple[QuestionRecord, ...]:
    """Held rows on ``machine_id`` whose request has ended or is gone, with no start in
    the last ``wait_seconds``: never-started first, then the oldest start."""
    terminal = sorted(state.value for state in RequestState.terminal())
    rows = transaction.execute(
        sql_local_work.SELECT_HELD_WORK,
        (
            machine_id,
            QuestionState.WAITING_ON_REQUEST.value,
            _cutoff(now, wait_seconds),
            *terminal,
            RequestState.OPEN.value,
            encode_timestamp(now),
        ),
    ).fetchall()
    return tuple(question_from_row(row) for row in rows)


def dead_claim_work(
    transaction: Transaction,
    machine_id: int,
    now: datetime,
    stale_seconds: float,
    wait_seconds: float,
) -> tuple[QuestionRecord, ...]:
    """Claimed rows on ``machine_id`` whose last write is ``stale_seconds`` old or
    older, with no start in the last ``wait_seconds``."""
    rows = transaction.execute(
        sql_local_work.SELECT_DEAD_CLAIM_WORK,
        (
            machine_id,
            QuestionState.CLAIMED.value,
            _cutoff(now, stale_seconds),
            _cutoff(now, wait_seconds),
        ),
    ).fetchall()
    return tuple(question_from_row(row) for row in rows)


def wake_candidates(
    transaction: Transaction, machine_id: int, now: datetime
) -> tuple[str, ...]:
    """Members with a marked open request and a wake command on a checkout on
    ``machine_id``: those a wake may be due for there (``wake_due`` decides)."""
    rows = transaction.execute(
        sql_local_work.SELECT_WAKE_CANDIDATES,
        (machine_id, RequestState.OPEN.value, encode_timestamp(now)),
    ).fetchall()
    return tuple(text(row[0], "messages.to_member") for row in rows)


def count_resume_start(transaction: Transaction, answer_seq: int) -> None:
    """Add one to the resumes ``claim_work`` has handed out for the answer."""
    transaction.execute(sql_local_work.COUNT_RESUME_START, (answer_seq,))
