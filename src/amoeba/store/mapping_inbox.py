"""Mapping between ``messages`` / ``inbox_submissions`` rows and their records.

The inbox's half of what ``mapping.py`` does for nodes, following
``mapping_journal.py``: rows arrive positionally in the column order declared
by ``sql_inbox``, and a row that cannot be mapped raises rather than yielding a
partially-populated object.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from amoeba.store import sql_inbox
from amoeba.store.inbox_models import (
    Channel,
    Message,
    SubmissionKind,
    SubmissionOutcome,
    SubmissionRecord,
)
from amoeba.store.mapping_journal import decode_mapping, decode_timestamp
from amoeba.store.models import UnknownVocabularyValueError


def _optional_text(value: object) -> str | None:
    return None if value is None else str(value)


def _integer(value: object, column: str) -> int:
    if not isinstance(value, int):
        raise UnknownVocabularyValueError(f"{column} is not an integer: {value!r}")
    return value


def _required_timestamp(value: object, column: str) -> datetime:
    decoded = decode_timestamp(value, column)
    if decoded is None:
        raise UnknownVocabularyValueError(f"{column} is NULL")
    return decoded


def _vocabulary[VocabularyT: (Channel, SubmissionKind, SubmissionOutcome)](
    value: object, vocabulary: type[VocabularyT], column: str
) -> VocabularyT:
    """Coerce a stored value into a closed inbox vocabulary, or raise."""
    if not isinstance(value, str):
        raise UnknownVocabularyValueError(f"{column} is not a string: {value!r}")
    try:
        return vocabulary(value)
    except ValueError as error:
        # Specific: the stored string is outside the vocabulary. Re-raised so
        # the caller never receives a defaulted record.
        raise UnknownVocabularyValueError(
            f"{column} value {value!r} is not a valid {vocabulary.__name__}"
        ) from error


def _require_width(row: Sequence[object], columns: tuple[str, ...], table: str) -> None:
    if len(row) != len(columns):
        raise UnknownVocabularyValueError(
            f"{table} row has {len(row)} columns, expected {len(columns)}"
        )


def map_submission_record(row: Sequence[object]) -> SubmissionRecord:
    """Map one ``inbox_submissions`` row to a :class:`SubmissionRecord`.

    Raises:
        UnknownVocabularyValueError: If the row is the wrong width or carries a
            value that cannot be mapped.
    """
    _require_width(row, sql_inbox.SUBMISSION_COLUMNS, sql_inbox.TABLE_INBOX_SUBMISSIONS)
    return SubmissionRecord(
        applied_seq=_integer(row[0], sql_inbox.COL_SUBMISSION_APPLIED_SEQ),
        id=str(row[1]),
        project_id=str(row[2]),
        kind=_vocabulary(row[3], SubmissionKind, sql_inbox.COL_SUBMISSION_KIND),
        submitted_by=str(row[4]),
        submitted_at=_required_timestamp(row[5], sql_inbox.COL_SUBMISSION_SUBMITTED_AT),
        payload=decode_mapping(row[6], sql_inbox.COL_SUBMISSION_PAYLOAD),
        outcome=_vocabulary(
            row[7], SubmissionOutcome, sql_inbox.COL_SUBMISSION_OUTCOME
        ),
        reason=_optional_text(row[8]),
        applied_at=decode_timestamp(row[9], sql_inbox.COL_SUBMISSION_APPLIED_AT),
    )


def map_message(row: Sequence[object]) -> Message:
    """Map one ``messages`` row to a :class:`Message`.

    Raises:
        UnknownVocabularyValueError: If the row is the wrong width or carries a
            value that cannot be mapped.
    """
    _require_width(row, sql_inbox.MESSAGE_COLUMNS, sql_inbox.TABLE_MESSAGES)
    return Message(
        seq=_integer(row[0], sql_inbox.COL_MESSAGE_SEQ),
        id=str(row[1]),
        project_id=str(row[2]),
        channel=_vocabulary(row[3], Channel, sql_inbox.COL_MESSAGE_CHANNEL),
        node_id=_optional_text(row[4]),
        blocked_state_id=_optional_text(row[5]),
        journal_entry_id=_optional_text(row[6]),
        submission_id=_optional_text(row[7]),
        payload=(
            None
            if row[8] is None
            else decode_mapping(row[8], sql_inbox.COL_MESSAGE_PAYLOAD)
        ),
        created_at=decode_timestamp(row[9], sql_inbox.COL_MESSAGE_CREATED_AT),
        acknowledged_at=decode_timestamp(
            row[10], sql_inbox.COL_MESSAGE_ACKNOWLEDGED_AT
        ),
        acknowledged_by=_optional_text(row[11]),
    )
