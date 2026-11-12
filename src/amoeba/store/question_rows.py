"""A ``QuestionRecord`` from a row of ``sql.QUESTION_COLUMNS``; shared by the
question reads in ``store.questions`` and ``store.question_closing``."""

from __future__ import annotations

from collections.abc import Sequence

from amoeba.answering.values import DeclineReason
from amoeba.store.models import QuestionKey, QuestionRecord
from amoeba.store.question_json import parse_evidence, parse_passages
from amoeba.store.row_values import (
    decode_timestamp,
    optional_text,
    optional_timestamp,
    text,
    vocabulary,
)
from amoeba.store.vocabulary import ClosedReason, QuestionState


def question_from_row(row: Sequence[object]) -> QuestionRecord:
    """A ``QuestionRecord`` from a row of ``sql.QUESTION_COLUMNS``."""
    return QuestionRecord(
        key=QuestionKey(
            run_id=text(row[0], "questions.run_id"),
            paused_at=text(row[1], "questions.paused_at"),
        ),
        member_id=text(row[2], "questions.member_id"),
        question=text(row[3], "questions.question"),
        checkout=text(row[4], "questions.checkout"),
        state=vocabulary(row[5], QuestionState, "questions.state"),
        answering_run_id=optional_text(row[6], "questions.answering_run_id"),
        waiting_reason=(
            None
            if row[7] is None
            else vocabulary(row[7], DeclineReason, "questions.waiting_reason")
        ),
        waiting_detail=optional_text(row[8], "questions.waiting_detail"),
        slice_label=optional_text(row[9], "questions.slice_label"),
        source_commit=optional_text(row[10], "questions.source_commit"),
        passages=None if row[11] is None else parse_passages(row[11]),
        evidence=None if row[12] is None else parse_evidence(row[12]),
        claimed_at=decode_timestamp(row[13], "questions.claimed_at"),
        updated_at=decode_timestamp(row[14], "questions.updated_at"),
        closed_reason=(
            None
            if row[15] is None
            else vocabulary(row[15], ClosedReason, "questions.closed_reason")
        ),
        closed_detail=optional_text(row[16], "questions.closed_detail"),
        closed_at=optional_timestamp(row[17], "questions.closed_at"),
    )
