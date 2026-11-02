"""Question records: the reads and the writers (slice 141).

Mixed into ``Store``; see ``store.py`` for the assembled public class.

Every write is one method in one ``BEGIN IMMEDIATE`` transaction and checks
``QUESTION_TRANSITIONS`` under the lock. The reads work through a read-only
handle.
"""

from __future__ import annotations

from collections.abc import Mapping

from amoeba.store import sql_inbox, sql_questions
from amoeba.store._base import isoformat, new_id, now
from amoeba.store._block_writer import BlockWriter
from amoeba.store.mapping_questions import map_question_record
from amoeba.store.models import (
    BLOCKED_STATUSES,
    BlockedKind,
    BlockedState,
    InvalidTransitionError,
)
from amoeba.store.question_models import (
    QUESTION_TRANSITIONS,
    AnsweredBy,
    DeclineReason,
    QuestionCatch,
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

    def record_question(
        self,
        catch: QuestionCatch,
        *,
        block_context: str,
        block_payload: Mapping[str, object] | None,
    ) -> QuestionRecord:
        """Write a question's ``HUMAN`` block and its record in one transaction.

        Idempotent per journal entry: a record that already exists for
        ``catch.source_entry_id`` is returned and nothing is written. On a node
        that is already blocked no block is written, and the record is born
        ``declined`` and linked to no block, so a PM answer to the other block is
        never taken for this question's (D1).

        Raises:
            NodeNotFoundError: The node does not exist.
            InvalidTransitionError: The node is done.
        """
        with self._connection:
            self._execute(sql_inbox.BEGIN_IMMEDIATE, ())
            existing = self._execute(
                sql_questions.SELECT_QUESTION_BY_ENTRY, (catch.source_entry_id,)
            ).fetchone()
            if existing is not None:
                return map_question_record(existing)
            node = self._require_node(catch.node_id)
            self._refuse_if_done(node)
            stamp = isoformat(now())
            blocked = node.status in BLOCKED_STATUSES
            block_id = (
                None
                if blocked
                else self._write_block(
                    node.id,
                    project_id=node.project_id,
                    kind=BlockedKind.HUMAN,
                    context=block_context,
                    timestamp=stamp,
                    payload=block_payload,
                )
            )
            question_id = self._insert_question(catch, block_id, blocked, stamp)
        return self._require_question(question_id)

    def _insert_question(
        self,
        catch: QuestionCatch,
        blocked_state_id: str | None,
        node_was_blocked: bool,
        timestamp: str,
    ) -> str:
        """Insert the record: ``pending`` on a new block, else ``declined``."""
        question_id = new_id()
        declined = node_was_blocked
        values: dict[str, object] = {
            sql_questions.COL_QUESTION_ID: question_id,
            sql_questions.COL_QUESTION_PROJECT_ID: catch.project_id,
            sql_questions.COL_QUESTION_NODE_ID: catch.node_id,
            sql_questions.COL_QUESTION_SOURCE_ENTRY_ID: catch.source_entry_id,
            sql_questions.COL_QUESTION_RUN_ID: catch.run_id,
            sql_questions.COL_QUESTION_STEP: catch.step,
            sql_questions.COL_QUESTION_TEXT: catch.question,
            sql_questions.COL_QUESTION_TRUNCATED: 1 if catch.truncated else 0,
            sql_questions.COL_QUESTION_BLOCKED_STATE_ID: blocked_state_id,
            sql_questions.COL_QUESTION_STATE: (
                QuestionState.DECLINED if declined else QuestionState.PENDING
            ).value,
            sql_questions.COL_QUESTION_ANSWERED_BY: None,
            sql_questions.COL_QUESTION_ANSWER: None,
            sql_questions.COL_QUESTION_DECLINE_REASON: (
                DeclineReason.NODE_ALREADY_BLOCKED.value if declined else None
            ),
            sql_questions.COL_QUESTION_CREATED_AT: timestamp,
            sql_questions.COL_QUESTION_UPDATED_AT: timestamp,
            sql_questions.COL_QUESTION_RESERVED_TERM: None,
        }
        self._execute(
            sql_questions.INSERT_QUESTION,
            tuple(values[column] for column in sql_questions.QUESTION_COLUMNS),
        )
        return question_id

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
                    None,
                    isoformat(now()),
                    question_id,
                ),
            )
        return self._require_question(question_id)

    def _settle_question_on_acknowledgment(
        self,
        state: BlockedState,
        *,
        applied_without_effect: bool,
        new_block_id: str | None,
        timestamp: str,
    ) -> None:
        """Settle the question on an acknowledged block, if it has one (D2).

        Runs inside ``acknowledge_resolution``'s transaction. Reads only store
        facts: whether the acknowledgment wrote a new block and whether it was
        applied with no effect, never who submitted it or what it decided.
        """
        row = self._execute(
            sql_questions.SELECT_QUESTION_BY_BLOCK, (state.id,)
        ).fetchone()
        if row is None:
            return
        record = map_question_record(row)
        if record.state is QuestionState.ANSWERED:
            return
        if new_block_id is not None:
            # A stop or a rejection re-blocked the node: the question follows.
            self._execute(
                sql_questions.UPDATE_QUESTION_BLOCK,
                (new_block_id, timestamp, record.id),
            )
        elif applied_without_effect:
            require_transition(record, QuestionState.ANSWERED)
            instructions = (
                None if state.resolution is None else state.resolution.instructions
            )
            self._execute(
                sql_questions.UPDATE_QUESTION_ANSWERED,
                (
                    QuestionState.ANSWERED.value,
                    AnsweredBy.PM.value,
                    instructions,
                    timestamp,
                    record.id,
                ),
            )

    def _require_question(self, question_id: str) -> QuestionRecord:
        record = self.question(question_id)
        if record is None:
            raise InvalidTransitionError(f"no question record {question_id!r}")
        return record
