"""Mapping between ``messages`` / ``inbox_submissions`` rows and their records.

The inbox's half of what ``mapping.py`` does for nodes, following
``mapping_journal.py``: rows arrive positionally in the column order declared
by ``sql_inbox``, and a row that cannot be mapped raises rather than yielding a
partially-populated object.
"""

from __future__ import annotations

from collections.abc import Sequence

from amoeba.store import sql_inbox
from amoeba.store.inbox_models import Channel, Message
from amoeba.store.mapping_journal import decode_mapping, decode_timestamp
from amoeba.store.models import UnknownVocabularyValueError


def _optional_text(value: object) -> str | None:
    return None if value is None else str(value)


def _channel(value: object) -> Channel:
    if not isinstance(value, str):
        raise UnknownVocabularyValueError(
            f"{sql_inbox.COL_MESSAGE_CHANNEL} is not a string: {value!r}"
        )
    try:
        return Channel(value)
    except ValueError as error:
        # Specific: the stored string is outside the vocabulary. Re-raised so
        # the caller never receives a defaulted message.
        raise UnknownVocabularyValueError(
            f"{sql_inbox.COL_MESSAGE_CHANNEL} value {value!r} is not a valid Channel"
        ) from error


def map_message(row: Sequence[object]) -> Message:
    """Map one ``messages`` row to a :class:`Message`.

    Raises:
        UnknownVocabularyValueError: If the row is the wrong width or carries a
            value that cannot be mapped.
    """
    if len(row) != len(sql_inbox.MESSAGE_COLUMNS):
        raise UnknownVocabularyValueError(
            f"{sql_inbox.TABLE_MESSAGES} row has {len(row)} columns, "
            f"expected {len(sql_inbox.MESSAGE_COLUMNS)}"
        )

    seq = row[0]
    if not isinstance(seq, int):
        raise UnknownVocabularyValueError(
            f"{sql_inbox.COL_MESSAGE_SEQ} is not an integer: {seq!r}"
        )

    return Message(
        seq=seq,
        id=str(row[1]),
        project_id=str(row[2]),
        channel=_channel(row[3]),
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
