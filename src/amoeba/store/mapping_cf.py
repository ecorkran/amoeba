"""Mapping between Context Forge link and snapshot rows and their records.

Follows ``mapping_feed.py``: rows arrive positionally in the column order
declared by ``sql_cf``, and a row that cannot be mapped raises rather than
yielding a partially-populated object.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import datetime
from typing import cast

from amoeba.store import sql_cf
from amoeba.store.cf_models import (
    CFLink,
    CFSnapshot,
    CFSnapshotInput,
    CFSnapshotOutcome,
)
from amoeba.store.mapping_journal import decode_mapping, decode_timestamp
from amoeba.store.models import UnknownVocabularyValueError
from amoeba.store.row_values import integer, optional_text, text


def _require_width(row: Sequence[object], columns: tuple[str, ...], table: str) -> None:
    if len(row) != len(columns):
        raise UnknownVocabularyValueError(
            f"{table} row has {len(row)} columns, expected {len(columns)}"
        )


def _timestamp(value: object, column: str) -> datetime:
    decoded = decode_timestamp(value, column)
    if decoded is None:
        raise UnknownVocabularyValueError(f"{column} is NULL")
    return decoded


def _outcome(value: object) -> CFSnapshotOutcome:
    word = text(value, sql_cf.COL_SNAPSHOT_OUTCOME)
    try:
        return CFSnapshotOutcome(word)
    except ValueError as error:
        # Specific: the stored string is outside the vocabulary. Re-raised so
        # the caller never receives a defaulted record.
        raise UnknownVocabularyValueError(
            f"{sql_cf.COL_SNAPSHOT_OUTCOME} value {word!r} is not a valid "
            "CFSnapshotOutcome"
        ) from error


def _changes(value: object) -> list[dict[str, object]]:
    """Decode the stored ``changed`` array of objects, or raise."""
    column = sql_cf.COL_SNAPSHOT_CHANGED
    if not isinstance(value, str):
        raise UnknownVocabularyValueError(f"{column} is not a string: {value!r}")
    try:
        decoded: object = json.loads(value)
    except json.JSONDecodeError as error:
        # Specific: a stored column that is not valid JSON is corruption.
        raise UnknownVocabularyValueError(f"{column} is not valid JSON") from error
    if not isinstance(decoded, list) or not all(
        isinstance(item, dict) for item in cast("list[object]", decoded)
    ):
        raise UnknownVocabularyValueError(f"{column} is not an array of objects")
    return cast("list[dict[str, object]]", decoded)


def map_link(row: Sequence[object]) -> CFLink:
    """Map one ``cf_links`` row to a :class:`CFLink`."""
    _require_width(row, sql_cf.LINK_COLUMNS, sql_cf.TABLE_CF_LINKS)
    c = dict(zip(sql_cf.LINK_COLUMNS, row, strict=True))
    return CFLink(
        project_id=text(c[sql_cf.COL_LINK_PROJECT_ID], sql_cf.COL_LINK_PROJECT_ID),
        cf_project_id=text(
            c[sql_cf.COL_LINK_CF_PROJECT_ID], sql_cf.COL_LINK_CF_PROJECT_ID
        ),
        linked_at=_timestamp(c[sql_cf.COL_LINK_LINKED_AT], sql_cf.COL_LINK_LINKED_AT),
    )


def map_snapshot(row: Sequence[object]) -> CFSnapshot:
    """Map one ``cf_snapshots`` row to a :class:`CFSnapshot`."""
    _require_width(row, sql_cf.SNAPSHOT_COLUMNS, sql_cf.TABLE_CF_SNAPSHOTS)
    c = dict(zip(sql_cf.SNAPSHOT_COLUMNS, row, strict=True))
    state = c[sql_cf.COL_SNAPSHOT_STATE]
    changed = c[sql_cf.COL_SNAPSHOT_CHANGED]
    return CFSnapshot(
        id=integer(c[sql_cf.COL_SNAPSHOT_ID], sql_cf.COL_SNAPSHOT_ID),
        project_id=text(
            c[sql_cf.COL_SNAPSHOT_PROJECT_ID], sql_cf.COL_SNAPSHOT_PROJECT_ID
        ),
        cf_project_id=text(
            c[sql_cf.COL_SNAPSHOT_CF_PROJECT_ID], sql_cf.COL_SNAPSHOT_CF_PROJECT_ID
        ),
        outcome=_outcome(c[sql_cf.COL_SNAPSHOT_OUTCOME]),
        state=(
            None if state is None else decode_mapping(state, sql_cf.COL_SNAPSHOT_STATE)
        ),
        changed=None if changed is None else _changes(changed),
        detail=optional_text(c[sql_cf.COL_SNAPSHOT_DETAIL], sql_cf.COL_SNAPSHOT_DETAIL),
        cf_updated_at=optional_text(
            c[sql_cf.COL_SNAPSHOT_CF_UPDATED_AT], sql_cf.COL_SNAPSHOT_CF_UPDATED_AT
        ),
        cf_version_label=text(
            c[sql_cf.COL_SNAPSHOT_CF_VERSION_LABEL],
            sql_cf.COL_SNAPSHOT_CF_VERSION_LABEL,
        ),
        observed_at=_timestamp(
            c[sql_cf.COL_SNAPSHOT_OBSERVED_AT], sql_cf.COL_SNAPSHOT_OBSERVED_AT
        ),
    )


def snapshot_parameters(snapshot: CFSnapshotInput) -> tuple[object, ...]:
    """Insert parameters for one snapshot, in ``SNAPSHOT_INSERT_COLUMNS`` order."""
    by_column: dict[str, object] = {
        sql_cf.COL_SNAPSHOT_PROJECT_ID: snapshot.project_id,
        sql_cf.COL_SNAPSHOT_CF_PROJECT_ID: snapshot.cf_project_id,
        sql_cf.COL_SNAPSHOT_OUTCOME: snapshot.outcome.value,
        sql_cf.COL_SNAPSHOT_STATE: (
            None if snapshot.state is None else json.dumps(dict(snapshot.state))
        ),
        sql_cf.COL_SNAPSHOT_CHANGED: (
            None
            if snapshot.changed is None
            else json.dumps([dict(change) for change in snapshot.changed])
        ),
        sql_cf.COL_SNAPSHOT_DETAIL: snapshot.detail,
        sql_cf.COL_SNAPSHOT_CF_UPDATED_AT: snapshot.cf_updated_at,
        sql_cf.COL_SNAPSHOT_CF_VERSION_LABEL: snapshot.cf_version_label,
        sql_cf.COL_SNAPSHOT_OBSERVED_AT: snapshot.observed_at.isoformat(),
    }
    return tuple(by_column[column] for column in sql_cf.SNAPSHOT_INSERT_COLUMNS)
