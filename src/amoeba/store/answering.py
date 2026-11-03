"""``begin_answering``: start an answering run for a pending question (slice 144, D5).

Mixed into ``Store``; see ``store.py`` for the assembled public class.

``journal_issue`` commits on its own, so following it with a separate
``pending -> answering`` write would let a crash between them leave a pending
record next to an in-flight ``sq_answer``, and the next tick would launch a second
run. Here one ``BEGIN IMMEDIATE`` transaction inserts the entry and moves the
record, or writes nothing.
"""

from __future__ import annotations

from amoeba.store import sql_inbox, sql_questions
from amoeba.store._base import isoformat, now
from amoeba.store.answer_submission import AnswerSubmissionOperations
from amoeba.store.journal import JournalOperations
from amoeba.store.journal_models import CommandKind
from amoeba.store.mapping_questions import (
    encode_passage_index,
    encode_text_list,
    map_question_record,
)
from amoeba.store.models import QuestionNotFoundError
from amoeba.store.question_models import (
    AnsweringLaunch,
    BeginOutcome,
    BeginStatus,
    QuestionRecord,
    QuestionState,
)
from amoeba.store.questions import require_transition


class AnsweringOperations(JournalOperations, AnswerSubmissionOperations):
    """Begins an answering run: the journal entry and the state change together."""

    def begin_answering(
        self, question_id: str, launch: AnsweringLaunch
    ) -> BeginOutcome:
        """Journal an ``sq_answer`` entry and move the record to ``answering``.

        Returns:
            ``begun`` with the entry and the record, ``settled`` (the record is not
            ``pending``) or ``block_resolved`` (someone resolved its block). The
            last two write nothing.

        Raises:
            QuestionNotFoundError: No record has this id.
            ValueError: ``launch.parameters`` lacks a key the ``sq_answer`` kind
                requires, or ``launch.node_id`` is not the record's node. Raised
                before any write.
        """
        with self._connection:
            self._execute(sql_inbox.BEGIN_IMMEDIATE, ())
            return self._begin_within(question_id, launch)

    def question_for_answering_entry(self, entry_id: str) -> QuestionRecord | None:
        """The record linked to an ``sq_answer`` entry, or ``None``."""
        row = self._execute(
            sql_questions.SELECT_QUESTION_BY_ANSWERING_ENTRY, (entry_id,)
        ).fetchone()
        return None if row is None else map_question_record(row)

    def _begin_within(self, question_id: str, launch: AnsweringLaunch) -> BeginOutcome:
        record = self.question(question_id)
        if record is None:
            raise QuestionNotFoundError(f"no question record {question_id!r}")
        if record.state is not QuestionState.PENDING:
            return BeginOutcome(BeginStatus.SETTLED, None, None)
        if launch.node_id != record.node_id:
            raise ValueError(
                f"launch is for node {launch.node_id!r}, but question "
                f"{question_id!r} belongs to node {record.node_id!r}"
            )
        if self._block_is_resolved(record):
            return BeginOutcome(BeginStatus.BLOCK_RESOLVED, None, None)
        entry = self._insert_entry_within(
            launch.node_id, CommandKind.SQ_ANSWER, launch.parameters
        )
        require_transition(record, QuestionState.ANSWERING)
        self._execute(
            sql_questions.UPDATE_QUESTION_BEGIN_ANSWERING,
            (
                QuestionState.ANSWERING.value,
                entry.id,
                launch.source_commit,
                encode_passage_index(launch.passages),
                encode_text_list(launch.dropped_pm_answers),
                isoformat(now()),
                question_id,
            ),
        )
        return BeginOutcome(
            BeginStatus.BEGUN, entry, self._require_question(question_id)
        )
