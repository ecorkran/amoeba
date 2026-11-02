"""``submit_answer``: the answerer's one gated submission (slice 142).

Mixed into ``Store``; see ``store.py`` for the assembled public class.

One ``BEGIN IMMEDIATE`` transaction reads the record, counts the run's prior
answers, runs the gate, and then either declines the question or writes the
resolution, its inbox submission row and the record's ``answered`` state together.
The gate runs under the write lock, so two submissions cannot both see a count
below the limit (D1).
"""

from __future__ import annotations

from amoeba.store import sql, sql_inbox, sql_questions
from amoeba.store._base import isoformat, new_id, now
from amoeba.store._submission_writer import SubmissionWriter
from amoeba.store.inbox_models import (
    RESOLUTION_BLOCKED_STATE_ID,
    RESOLUTION_DECISION,
    RESOLUTION_DETAIL,
    RESOLUTION_INSTRUCTIONS,
    SubmissionKind,
    SubmissionOutcome,
)
from amoeba.store.mapping import map_blocked_state
from amoeba.store.models import QuestionNotFoundError, StoreIntegrityError
from amoeba.store.question_models import (
    ANSWER_DECISION,
    AnsweredBy,
    AnswerGate,
    AnswerOutcome,
    AnswerSubmission,
    GateRefusal,
    QuestionRecord,
    QuestionState,
)
from amoeba.store.questions import QuestionOperations, require_transition

#: The states a record can be answered or declined from.
_OPEN_STATES = frozenset({QuestionState.PENDING, QuestionState.ANSWERING})


def _require_text(value: str, name: str) -> None:
    if not value.strip():
        raise ValueError(f"{name} must not be blank")


class AnswerSubmissionOperations(QuestionOperations, SubmissionWriter):
    """Submits the answerer's answer, or declines the question, atomically."""

    def submit_answer(
        self,
        question_id: str,
        *,
        answer: str,
        instructions: str,
        detail: str,
        gate: AnswerGate,
    ) -> AnswerSubmission:
        """Gate and submit one answer, or decline the question, in one transaction.

        The store writes ``ANSWER_DECISION`` as the decision and the answerer as
        ``resolved_by`` and ``submitted_by``; the caller supplies neither.
        ``gate`` is called once, under the write lock, with the record's
        question and the run's prior answerer answers. An exception from it
        rolls the transaction back and propagates.

        Returns:
            ``submitted`` (slot filled, submission row and ``answered`` record
            written), ``declined`` (the gate refused; slot untouched),
            ``block_resolved`` (someone resolved the block first; nothing
            written) or ``settled`` (the record is no longer open; nothing
            written).

        Raises:
            ValueError: A blank ``answer``, ``instructions`` or ``detail``, or a
                record with no question text.
            QuestionNotFoundError: No record has this id.
        """
        _require_text(answer, "answer")
        _require_text(instructions, "instructions")
        _require_text(detail, "detail")
        with self._connection:
            self._execute(sql_inbox.BEGIN_IMMEDIATE, ())
            outcome = self._gate_and_write(
                question_id, answer, instructions, detail, gate
            )
        return AnswerSubmission(outcome, self._require_question(question_id))

    def _gate_and_write(
        self,
        question_id: str,
        answer: str,
        instructions: str,
        detail: str,
        gate: AnswerGate,
    ) -> AnswerOutcome:
        """The transaction body: decide, then write the one outcome."""
        record = self.question(question_id)
        if record is None:
            raise QuestionNotFoundError(f"no question record {question_id!r}")
        if record.state not in _OPEN_STATES:
            return AnswerOutcome.SETTLED
        if record.question is None:
            raise ValueError(f"question {question_id!r} has no question text")
        if self._block_is_resolved(record):
            return AnswerOutcome.BLOCK_RESOLVED
        refusal = gate(record.question, self._prior_answers(record))
        if refusal is not None:
            self._write_decline(record, refusal)
            return AnswerOutcome.DECLINED
        return self._write_answer(record, answer, instructions, detail)

    def _block_is_resolved(self, record: QuestionRecord) -> bool:
        """Whether the record's block has been resolved by anyone."""
        if record.blocked_state_id is None:
            raise StoreIntegrityError(
                f"open question {record.id!r} is linked to no block"
            )
        row = self._execute(
            sql.SELECT_BLOCKED_STATE_BY_ID, (record.blocked_state_id,)
        ).fetchone()
        if row is None:
            raise StoreIntegrityError(
                f"question {record.id!r} points at missing block "
                f"{record.blocked_state_id!r}"
            )
        return map_blocked_state(row).is_resolved

    def _prior_answers(self, record: QuestionRecord) -> int:
        row = self._execute(
            sql_questions.COUNT_ANSWERER_ANSWERS_IN_RUN,
            (
                record.project_id,
                record.run_id,
                QuestionState.ANSWERED.value,
                AnsweredBy.ANSWERER.value,
                record.id,
            ),
        ).fetchone()
        return int(row[0])

    def _write_decline(self, record: QuestionRecord, refusal: GateRefusal) -> None:
        """Decline in this transaction. ``decline_question`` opens its own."""
        require_transition(record, QuestionState.DECLINED)
        self._execute(
            sql_questions.UPDATE_QUESTION_DECLINED,
            (
                QuestionState.DECLINED.value,
                refusal.reason.value,
                refusal.reserved_term,
                isoformat(now()),
                record.id,
            ),
        )

    def _write_answer(
        self, record: QuestionRecord, answer: str, instructions: str, detail: str
    ) -> AnswerOutcome:
        """Fill the slot, record the submission, and mark the record answered."""
        require_transition(record, QuestionState.ANSWERED)
        timestamp = isoformat(now())
        filled = self._write_resolution(
            record.node_id,
            resolved_by=AnsweredBy.ANSWERER.value,
            detail=detail,
            timestamp=timestamp,
            decision=ANSWER_DECISION,
            instructions=instructions,
            awaits_runner=True,
        )
        if not filled:
            # Nothing was written: the block was resolved after all.
            return AnswerOutcome.BLOCK_RESOLVED
        self._insert_submission(
            submission_id=new_id(),
            project_id=record.project_id,
            kind=SubmissionKind.RESOLUTION,
            submitted_by=AnsweredBy.ANSWERER.value,
            submitted_at=timestamp,
            payload={
                RESOLUTION_BLOCKED_STATE_ID: record.blocked_state_id,
                RESOLUTION_DETAIL: detail,
                RESOLUTION_DECISION: ANSWER_DECISION,
                RESOLUTION_INSTRUCTIONS: instructions,
            },
            outcome=SubmissionOutcome.APPLIED,
            reason=None,
            applied_at=timestamp,
        )
        self._execute(
            sql_questions.UPDATE_QUESTION_ANSWERED,
            (
                QuestionState.ANSWERED.value,
                AnsweredBy.ANSWERER.value,
                answer,
                timestamp,
                record.id,
            ),
        )
        return AnswerOutcome.SUBMITTED
