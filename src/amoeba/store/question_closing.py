"""Closing questions and reading the open ones (slice 228, D4, D5).

A question is *open* when it is ``claimed`` or ``waiting_on_pm``, or ``answered`` with
its latest answer unresumed (``resume_outcome`` null or ``refused``). Every write here
is a compare-and-set, so a concurrent ``answer``, ``dismiss`` or settle wins and the
loser learns it from the return value. Every function takes an open transaction;
none is held across a subprocess.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from amoeba.store import sql
from amoeba.store.answers import latest_answer, mark_not_delivered
from amoeba.store.errors import StoreRowError
from amoeba.store.models import QuestionKey, QuestionRecord
from amoeba.store.question_rows import question_from_row
from amoeba.store.row_values import encode_timestamp, text
from amoeba.store.store import Transaction
from amoeba.store.vocabulary import ClosedReason, QuestionState, ResumeOutcome

#: The bound values of the open-row clause: claimed, waiting, answered, refused.
_OPEN_PARAMETERS = (
    QuestionState.CLAIMED.value,
    QuestionState.WAITING_ON_PM.value,
    QuestionState.ANSWERED.value,
    ResumeOutcome.REFUSED.value,
)
#: The detail ``dismiss`` gives an answer it makes ``not_delivered``.
DISMISSED_DETAIL = "dismissed"


def close_question(  # noqa: PLR0913 - the compare-and-set's named inputs
    transaction: Transaction,
    key: QuestionKey,
    reason: ClosedReason,
    detail: str | None,
    expected_state: QuestionState,
    expected_updated_at: datetime,
    now: datetime,
) -> bool:
    """Close the question if its ``state`` and ``updated_at`` are still what the
    caller read. True if this call closed it."""
    moment = encode_timestamp(now)
    cursor = transaction.execute(
        sql.CLOSE_QUESTION,
        (
            QuestionState.CLOSED.value,
            reason.value,
            detail,
            moment,
            moment,
            key.run_id,
            key.paused_at,
            expected_state.value,
            encode_timestamp(expected_updated_at),
        ),
    )
    return cursor.rowcount == 1


def dismiss_question(
    transaction: Transaction,
    current: QuestionRecord,
    detail: str,
    *,
    now: datetime,
) -> bool:
    """Close the question ``current`` as ``dismissed``, with ``detail`` as the reason
    given.

    ``claimed`` and ``waiting_on_pm`` close. ``answered`` with an unresumed latest
    answer closes too, and in the same transaction that answer becomes
    ``not_delivered`` (detail ``dismissed``), unless its resume has started and not
    ended. Anything else, including a delivered answer and a question already
    ``closed``, is refused: False, nothing written.
    ``current`` is the row as the caller read it in this transaction; the write is a
    compare-and-set against it.
    """
    key = current.key
    match current.state:
        case QuestionState.CLAIMED | QuestionState.WAITING_ON_PM:
            return close_question(
                transaction,
                key,
                ClosedReason.DISMISSED,
                detail,
                current.state,
                current.updated_at,
                now,
            )
        case QuestionState.ANSWERED:
            latest = latest_answer(transaction, key)
            if latest is None or latest.resume_outcome not in (
                None,
                ResumeOutcome.REFUSED,
            ):
                return False
            if latest.resume_outcome is None and latest.resume_started_at is not None:
                return False  # a resume is in flight; its own outcome is the exit
            closed = close_question(
                transaction,
                key,
                ClosedReason.DISMISSED,
                detail,
                QuestionState.ANSWERED,
                current.updated_at,
                now,
            )
            if not closed:
                return False
            if not mark_not_delivered(
                transaction, latest.seq, DISMISSED_DETAIL, now=now
            ):
                # The write lock is held and the outcome was just read as open, so
                # this cannot happen; raising rolls back the close rather than
                # returning "refused" after it wrote.
                raise StoreRowError(
                    f"answer {latest.seq} of {key.run_id} at {key.paused_at} "
                    "could not be marked not_delivered after its question closed"
                )
            return True
        case QuestionState.CLOSED:
            return False


def open_rows_of_run(
    transaction: Transaction, run_id: str
) -> tuple[QuestionRecord, ...]:
    """The run's open questions, oldest first."""
    rows = transaction.execute(
        sql.SELECT_OPEN_ROWS_OF_RUN, (run_id, *_OPEN_PARAMETERS)
    ).fetchall()
    return tuple(question_from_row(row) for row in rows)


def sweep_candidates(
    transaction: Transaction, member_ids: Sequence[str]
) -> tuple[QuestionRecord, ...]:
    """The open questions of these members, oldest first."""
    if not member_ids:
        return ()
    rows = transaction.execute(
        sql.select_open_rows_of_members(len(member_ids)),
        (*member_ids, *_OPEN_PARAMETERS),
    ).fetchall()
    return tuple(question_from_row(row) for row in rows)


def member_open_questions(
    transaction: Transaction, member_id: str
) -> tuple[QuestionRecord, ...]:
    """The member's open questions, for ``set_up`` to refuse a removal (228 D8)."""
    rows = transaction.execute(
        sql.SELECT_OPEN_ROWS_OF_MEMBER, (member_id, *_OPEN_PARAMETERS)
    ).fetchall()
    return tuple(question_from_row(row) for row in rows)


def open_answering_run_ids(transaction: Transaction) -> frozenset[str]:
    """Answering run ids of open questions: their scratch and logs are evidence."""
    rows = transaction.execute(sql.SELECT_OPEN_ANSWERING_RUN_IDS, _OPEN_PARAMETERS)
    return frozenset(text(row[0], "questions.answering_run_id") for row in rows)


def run_ids_with_open_question(transaction: Transaction) -> frozenset[str]:
    """Run ids that have an open question: their resume logs are evidence."""
    rows = transaction.execute(sql.SELECT_RUN_IDS_WITH_OPEN_QUESTION, _OPEN_PARAMETERS)
    return frozenset(text(row[0], "questions.run_id") for row in rows)
