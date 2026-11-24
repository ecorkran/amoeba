"""What ``rm-machine`` closes on the machine it removes (slice 262, D13).

In the caller's one transaction, before the machine row goes: every open question on
the machine closes as ``machine_removed``; each such answered question's latest answer
is marked ``not_delivered`` and its resume claim cleared; every unended wake ends as
``machine_removed``; and the machine's question and wake rows lose their machine (and
the wakes their log path, which means nothing without the machine). The rows stay as
history; a later ``answer`` to one of those questions is not delivered (D7).
"""

from __future__ import annotations

from datetime import datetime
from typing import Final

from amoeba.store import sql_local_work
from amoeba.store.answers import latest_answer, mark_not_delivered
from amoeba.store.question_closing import close_question, open_rows_of_machine
from amoeba.store.row_values import encode_timestamp
from amoeba.store.store import Transaction
from amoeba.store.vocabulary import ClosedReason, QuestionState, WakeOutcome

#: The detail every closed question, undelivered answer and ended wake carries.
REMOVED_DETAIL: Final = "its machine {name} was removed"


def close_machine_work(
    transaction: Transaction, machine_id: int, name: str, now: datetime
) -> None:
    """Close what waits on the machine ``machine_id`` (named ``name``)."""
    detail = REMOVED_DETAIL.format(name=name)
    for question in open_rows_of_machine(transaction, machine_id):
        if question.state is QuestionState.ANSWERED:
            latest = latest_answer(transaction, question.key)
            if latest is not None:
                mark_not_delivered(transaction, latest.seq, detail, now=now)
                transaction.execute(sql_local_work.CLEAR_RESUME_CLAIM, (latest.seq,))
        close_question(
            transaction,
            question.key,
            ClosedReason.MACHINE_REMOVED,
            detail,
            question.state,
            question.updated_at,
            now,
        )
    transaction.execute(
        sql_local_work.END_WAKES_OF_MACHINE,
        (encode_timestamp(now), WakeOutcome.MACHINE_REMOVED.value, detail, machine_id),
    )
    transaction.execute(sql_local_work.RELEASE_QUESTIONS_OF_MACHINE, (machine_id,))
    transaction.execute(sql_local_work.RELEASE_WAKES_OF_MACHINE, (machine_id,))
