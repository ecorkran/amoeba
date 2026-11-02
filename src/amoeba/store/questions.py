"""Question records: the reads and the writers (slice 141).

Mixed into ``Store``; see ``store.py`` for the assembled public class.

Every write is one method in one ``BEGIN IMMEDIATE`` transaction and checks
``QUESTION_TRANSITIONS`` under the lock. The reads work through a read-only
handle.
"""

from __future__ import annotations

from amoeba.store import sql_inbox, sql_questions
from amoeba.store._base import isoformat, now
from amoeba.store._block_writer import BlockWriter
from amoeba.store.mapping_questions import map_question_record
from amoeba.store.models import InvalidTransitionError
from amoeba.store.question_models import (
    QUESTION_TRANSITIONS,
    DeclineReason,
    QuestionRecord,
    QuestionState,
)


def require_transition(record: QuestionRecord, target: QuestionState) -> None:
    """Refuse a state change the transition table does not allow."""
    if target not in QUESTION_TRANSITIONS[record.state]:
        raise InvalidTransitionError(
            f"question {record.id!r} cannot go from "
            f"{record.state.value!r} to {target.value!r}"
        )


class QuestionOperations(BlockWriter):
    """Reads and writes the question records."""

    def question(self, question_id: str) -> QuestionRecord | None:
        """One record by id, or ``None``."""
        row = self._execute(sql_questions.SELECT_QUESTION_BY_ID, (question_id,))
        found = row.fetchone()
        return None if found is None else map_question_record(found)

    def questions(
        self,
        project_id: str,
        *,
        state: QuestionState | None = None,
        node_id: str | None = None,
    ) -> list[QuestionRecord]:
        """The project's records, oldest first, optionally by state and node."""
        state_value = None if state is None else state.value
        rows = self._execute(
            sql_questions.SELECT_QUESTIONS,
            (project_id, state_value, state_value, node_id, node_id),
        ).fetchall()
        return [map_question_record(row) for row in rows]

    def pending_questions(self, project_id: str) -> list[QuestionRecord]:
        """The project's ``pending`` records, oldest first, by the state index."""
        rows = self._execute(
            sql_questions.SELECT_QUESTIONS_IN_STATE,
            (project_id, QuestionState.PENDING.value),
        ).fetchall()
        return [map_question_record(row) for row in rows]

    def question_for_block(self, blocked_state_id: str) -> QuestionRecord | None:
        """The record linked to a blocked state, or ``None``."""
        row = self._execute(
            sql_questions.SELECT_QUESTION_BY_BLOCK, (blocked_state_id,)
        ).fetchone()
        return None if row is None else map_question_record(row)

    def decline_question(
        self, question_id: str, *, reason: DeclineReason
    ) -> QuestionRecord:
        """Mark a record ``declined``. Record-only: no block, no node change.

        Raises:
            InvalidTransitionError: The record does not exist, or its state does
                not allow ``declined``. Nothing is written.
        """
        with self._connection:
            self._execute(sql_inbox.BEGIN_IMMEDIATE, ())
            record = self._require_question(question_id)
            require_transition(record, QuestionState.DECLINED)
            self._execute(
                sql_questions.UPDATE_QUESTION_DECLINED,
                (
                    QuestionState.DECLINED.value,
                    reason.value,
                    isoformat(now()),
                    question_id,
                ),
            )
        return self._require_question(question_id)

    def _require_question(self, question_id: str) -> QuestionRecord:
        record = self.question(question_id)
        if record is None:
            raise InvalidTransitionError(f"no question record {question_id!r}")
        return record
