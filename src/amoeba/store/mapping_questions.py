"""Mapping between ``question_records`` rows and :class:`QuestionRecord`.

Follows ``mapping_runner.py``: rows arrive positionally in the column order
declared by ``sql_questions``, and a row that cannot be mapped raises rather than
yielding a partially-populated object.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from enum import StrEnum

from amoeba.store import sql_questions
from amoeba.store.mapping_journal import decode_timestamp
from amoeba.store.models import UnknownVocabularyValueError
from amoeba.store.question_models import (
    AnsweredBy,
    DeclineReason,
    QuestionRecord,
    QuestionState,
)
from amoeba.store.row_values import optional_text, text


def _vocabulary[VocabularyT: StrEnum](
    value: object, vocabulary: type[VocabularyT], column: str
) -> VocabularyT:
    """Coerce a stored value into a closed question vocabulary, or raise."""
    try:
        return vocabulary(text(value, column))
    except ValueError as error:
        # Specific: the stored string is outside the vocabulary. Re-raised so
        # the caller never receives a defaulted record.
        raise UnknownVocabularyValueError(
            f"{column} value {value!r} is not a valid {vocabulary.__name__}"
        ) from error


def _optional_vocabulary[VocabularyT: StrEnum](
    value: object, vocabulary: type[VocabularyT], column: str
) -> VocabularyT | None:
    return None if value is None else _vocabulary(value, vocabulary, column)


def _required_timestamp(value: object, column: str) -> datetime:
    decoded = decode_timestamp(value, column)
    if decoded is None:
        raise UnknownVocabularyValueError(f"{column} is NULL")
    return decoded


def _flag(value: object, column: str) -> bool:
    if value not in (0, 1):
        raise UnknownVocabularyValueError(f"{column} is not 0 or 1: {value!r}")
    return value == 1


def map_question_record(row: Sequence[object]) -> QuestionRecord:
    """Map one ``question_records`` row.

    Raises:
        UnknownVocabularyValueError: If the row is the wrong width or carries a
            value outside a closed vocabulary.
    """
    columns = sql_questions.QUESTION_COLUMNS
    if len(row) != len(columns):
        raise UnknownVocabularyValueError(
            f"{sql_questions.TABLE_QUESTION_RECORDS} row has {len(row)} columns, "
            f"expected {len(columns)}"
        )
    return QuestionRecord(
        id=text(row[0], sql_questions.COL_QUESTION_ID),
        project_id=text(row[1], sql_questions.COL_QUESTION_PROJECT_ID),
        node_id=text(row[2], sql_questions.COL_QUESTION_NODE_ID),
        source_entry_id=text(row[3], sql_questions.COL_QUESTION_SOURCE_ENTRY_ID),
        run_id=text(row[4], sql_questions.COL_QUESTION_RUN_ID),
        step=optional_text(row[5], sql_questions.COL_QUESTION_STEP),
        question=optional_text(row[6], sql_questions.COL_QUESTION_TEXT),
        truncated=_flag(row[7], sql_questions.COL_QUESTION_TRUNCATED),
        blocked_state_id=optional_text(
            row[8], sql_questions.COL_QUESTION_BLOCKED_STATE_ID
        ),
        state=_vocabulary(row[9], QuestionState, sql_questions.COL_QUESTION_STATE),
        answered_by=_optional_vocabulary(
            row[10], AnsweredBy, sql_questions.COL_QUESTION_ANSWERED_BY
        ),
        answer=optional_text(row[11], sql_questions.COL_QUESTION_ANSWER),
        decline_reason=_optional_vocabulary(
            row[12], DeclineReason, sql_questions.COL_QUESTION_DECLINE_REASON
        ),
        created_at=_required_timestamp(row[13], sql_questions.COL_QUESTION_CREATED_AT),
        updated_at=_required_timestamp(row[14], sql_questions.COL_QUESTION_UPDATED_AT),
        reserved_term=optional_text(row[15], sql_questions.COL_QUESTION_RESERVED_TERM),
    )
