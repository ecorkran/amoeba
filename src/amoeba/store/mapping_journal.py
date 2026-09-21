"""Mapping between ``command_journal`` rows and :class:`JournalEntry`.

The journal's half of what ``mapping.py`` does for nodes and blocked states,
kept in its own module for the same reason ``sql_journal.py`` is a sibling of
``sql.py``: one definition site per concern rather than one growing file.

A row that cannot be mapped raises rather than yielding a partially-populated
object — "unknown is a value, not a default" at the storage boundary. Rows
arrive as positional tuples in the column order declared by
``sql_journal.JOURNAL_COLUMNS``, which every journal statement selects with.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import datetime

from amoeba.store import sql_journal
from amoeba.store.journal_models import (
    CommandKind,
    JournalEntry,
    JournalOutcome,
    JournalResolver,
)
from amoeba.store.models import UnknownVocabularyValueError


def decode_mapping(value: object, column: str) -> Mapping[str, object]:
    """Decode a stored JSON object column, or raise.

    A column that does not hold a JSON object is corruption, not a reason to
    substitute an empty mapping: "unknown is a value, not a default" at the
    storage boundary, exactly as in ``mapping.py``.
    """
    if not isinstance(value, str):
        raise UnknownVocabularyValueError(f"{column} is not a string: {value!r}")

    try:
        decoded = json.loads(value)
    except json.JSONDecodeError as error:
        # Specific: a stored column that is not valid JSON is corruption.
        raise UnknownVocabularyValueError(
            f"{column} is not valid JSON: {value!r}"
        ) from error

    if not isinstance(decoded, dict):
        raise UnknownVocabularyValueError(f"{column} is not a JSON object: {value!r}")

    # json.loads types its result as Any, so the keys are checked rather than
    # asserted: a non-string key cannot come from json.dumps of a mapping this
    # package wrote, and would mean the column was edited by something else.
    narrowed: dict[str, object] = {}
    for key, item in decoded.items():  # pyright: ignore[reportUnknownVariableType]
        if not isinstance(key, str):
            raise UnknownVocabularyValueError(f"{column} has a non-string key: {key!r}")
        narrowed[key] = item

    return narrowed


def _vocabulary[VocabularyT: (CommandKind, JournalOutcome, JournalResolver)](
    value: object, vocabulary: type[VocabularyT], column: str
) -> VocabularyT:
    """Coerce a stored value into a closed journal vocabulary, or raise."""
    if not isinstance(value, str):
        raise UnknownVocabularyValueError(f"{column} is not a string: {value!r}")
    try:
        return vocabulary(value)
    except ValueError as error:
        # Specific: the stored string is outside the vocabulary. Re-raised so
        # the caller never receives a defaulted entry.
        raise UnknownVocabularyValueError(
            f"{column} value {value!r} is not a valid {vocabulary.__name__}"
        ) from error


def _timestamp(value: object, column: str) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise UnknownVocabularyValueError(f"{column} is not a string: {value!r}")
    try:
        return datetime.fromisoformat(value)
    except ValueError as error:
        # Specific: a stored timestamp that is not ISO-8601 is corruption.
        raise UnknownVocabularyValueError(
            f"{column} is not an ISO-8601 timestamp: {value!r}"
        ) from error


def map_journal_entry(row: Sequence[object]) -> JournalEntry:
    """Map one ``command_journal`` row to a :class:`JournalEntry`.

    Rows arrive positionally in the order declared by
    ``sql_journal.JOURNAL_COLUMNS``, which every journal statement selects with.

    Raises:
        UnknownVocabularyValueError: If the row is the wrong width or carries a
            value that cannot be mapped.
    """
    if len(row) != len(sql_journal.JOURNAL_COLUMNS):
        raise UnknownVocabularyValueError(
            f"{sql_journal.TABLE_COMMAND_JOURNAL} row has {len(row)} columns, "
            f"expected {len(sql_journal.JOURNAL_COLUMNS)}"
        )

    outcome_value = row[6]
    resolver_value = row[9]

    return JournalEntry(
        id=str(row[0]),
        project_id=str(row[1]),
        node_id=str(row[2]),
        kind=_vocabulary(row[3], CommandKind, sql_journal.COL_JOURNAL_KIND),
        parameters=decode_mapping(row[4], sql_journal.COL_JOURNAL_PARAMETERS),
        issued_at=_timestamp(row[5], sql_journal.COL_JOURNAL_ISSUED_AT),
        outcome=(
            None
            if outcome_value is None
            else _vocabulary(
                outcome_value, JournalOutcome, sql_journal.COL_JOURNAL_OUTCOME
            )
        ),
        result=(
            None
            if row[7] is None
            else decode_mapping(row[7], sql_journal.COL_JOURNAL_RESULT)
        ),
        resolved_at=_timestamp(row[8], sql_journal.COL_JOURNAL_RESOLVED_AT),
        resolved_by=(
            None
            if resolver_value is None
            else _vocabulary(
                resolver_value, JournalResolver, sql_journal.COL_JOURNAL_RESOLVED_BY
            )
        ),
    )
