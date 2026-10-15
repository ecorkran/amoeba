"""Mapping between feed and detection rows and their records.

Follows ``mapping_journal.py``: rows arrive positionally in the column order
declared by ``sql_feed``, and a row that cannot be mapped raises rather than
yielding a partially-populated object.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from amoeba.store import sql_feed
from amoeba.store.feed_models import (
    Change,
    ChangeKind,
    DetectedReview,
    DetectionOutcome,
    ReviewWatch,
)
from amoeba.store.mapping_journal import decode_mapping, decode_timestamp
from amoeba.store.models import UnknownVocabularyValueError


def _require_width(row: Sequence[object], columns: tuple[str, ...], table: str) -> None:
    if len(row) != len(columns):
        raise UnknownVocabularyValueError(
            f"{table} row has {len(row)} columns, expected {len(columns)}"
        )


def _vocabulary[VocabularyT: (ChangeKind, DetectionOutcome)](
    value: object, vocabulary: type[VocabularyT], column: str
) -> VocabularyT:
    """Coerce a stored value into a closed feed vocabulary, or raise."""
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


def _integer(value: object, column: str) -> int:
    # bool is an int subclass; a stored boolean is not a sequence number.
    if not isinstance(value, int) or isinstance(value, bool):
        raise UnknownVocabularyValueError(f"{column} is not an integer: {value!r}")
    return value


def _optional_text(value: object) -> str | None:
    return None if value is None else str(value)


def _required_timestamp(value: object, column: str) -> datetime:
    decoded = decode_timestamp(value, column)
    if decoded is None:
        raise UnknownVocabularyValueError(f"{column} is NULL")
    return decoded


def _flag(value: object, column: str) -> bool:
    if value not in (0, 1):
        raise UnknownVocabularyValueError(f"{column} is not 0 or 1: {value!r}")
    return value == 1


def map_change(row: Sequence[object]) -> Change:
    """Map one ``changes`` row to a :class:`Change`.

    Raises:
        UnknownVocabularyValueError: If the row is the wrong width, carries an
            unknown kind, or holds a payload that is not a JSON object.
    """
    _require_width(row, sql_feed.CHANGE_COLUMNS, sql_feed.TABLE_CHANGES)
    return Change(
        seq=_integer(row[0], sql_feed.COL_CHANGE_SEQ),
        project_id=str(row[1]),
        kind=_vocabulary(row[2], ChangeKind, sql_feed.COL_CHANGE_KIND),
        node_id=_optional_text(row[3]),
        subject_id=str(row[4]),
        payload=decode_mapping(row[5], sql_feed.COL_CHANGE_PAYLOAD),
        recorded_at=_required_timestamp(row[6], sql_feed.COL_CHANGE_RECORDED_AT),
    )


def map_watch(row: Sequence[object]) -> ReviewWatch:
    """Map one ``review_watches`` row to a :class:`ReviewWatch`."""
    _require_width(row, sql_feed.WATCH_COLUMNS, sql_feed.TABLE_REVIEW_WATCHES)
    return ReviewWatch(
        project_id=str(row[0]),
        reviews_dir=str(row[1]),
        active=_flag(row[2], sql_feed.COL_WATCH_ACTIVE),
        registered_at=_required_timestamp(row[3], sql_feed.COL_WATCH_REGISTERED_AT),
        baselined_at=decode_timestamp(row[4], sql_feed.COL_WATCH_BASELINED_AT),
        updated_at=_required_timestamp(row[5], sql_feed.COL_WATCH_UPDATED_AT),
    )


def map_detected_review(row: Sequence[object]) -> DetectedReview:
    """Map one ``detected_reviews`` row to a :class:`DetectedReview`."""
    _require_width(row, sql_feed.DETECTION_COLUMNS, sql_feed.TABLE_DETECTED_REVIEWS)
    return DetectedReview(
        id=_integer(row[0], sql_feed.COL_DETECTION_ID),
        project_id=str(row[1]),
        path=str(row[2]),
        digest=str(row[3]),
        outcome=_vocabulary(row[4], DetectionOutcome, sql_feed.COL_DETECTION_OUTCOME),
        node_id=_optional_text(row[5]),
        verdict_id=_optional_text(row[6]),
        record_id=_optional_text(row[7]),
        detail=_optional_text(row[8]),
        detected_at=_required_timestamp(row[9], sql_feed.COL_DETECTION_DETECTED_AT),
    )
