"""The single mapping layer between SQL rows and typed dataclasses.

Mapping lives in exactly one place. A row that cannot be mapped raises rather
than yielding a partially-populated object: "unknown is a value, not a default"
at the storage boundary. That is what makes a hand-edited or corrupted status
surface instead of quietly becoming something valid-looking.

Rows arrive as positional tuples in the column order declared by
``sql.NODE_COLUMNS`` and ``sql.BLOCKED_STATE_COLUMNS``, which every statement in
``sql`` selects with. The order is declared once there and consumed here.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from amoeba.store import sql
from amoeba.store.models import (
    BlockedKind,
    BlockedState,
    CFReference,
    Node,
    NodeKind,
    NodeStatus,
    Resolution,
    SQReference,
    UnknownVocabularyValueError,
)


def _vocabulary[VocabularyT: (NodeStatus, NodeKind, BlockedKind)](
    value: object, vocabulary: type[VocabularyT], column: str
) -> VocabularyT:
    """Coerce a stored value into a closed vocabulary, or raise."""
    if not isinstance(value, str):
        raise UnknownVocabularyValueError(f"{column} is not a string: {value!r}")
    try:
        return vocabulary(value)
    except ValueError as error:
        # Specific: the stored string is outside the vocabulary. Re-raised as a
        # store error so the caller never receives a defaulted object.
        raise UnknownVocabularyValueError(
            f"{column} value {value!r} is not a valid {vocabulary.__name__}"
        ) from error


def _text(value: object, column: str) -> str:
    if not isinstance(value, str):
        raise UnknownVocabularyValueError(f"{column} is not a string: {value!r}")
    return value


def _optional_text(value: object, column: str) -> str | None:
    return None if value is None else _text(value, column)


def _timestamp(value: object, column: str) -> datetime | None:
    if value is None:
        return None
    text = _text(value, column)
    try:
        return datetime.fromisoformat(text)
    except ValueError as error:
        # Specific: a stored timestamp that is not ISO-8601 is corruption.
        raise UnknownVocabularyValueError(
            f"{column} is not an ISO-8601 timestamp: {text!r}"
        ) from error


def _require_width(row: Sequence[object], expected: int, what: str) -> None:
    if len(row) != expected:
        raise UnknownVocabularyValueError(
            f"{what} row has {len(row)} columns, expected {expected}"
        )


def map_node(row: Sequence[object]) -> Node:
    """Map one ``nodes`` row to a :class:`~amoeba.store.models.Node`.

    Raises:
        UnknownVocabularyValueError: If the row is the wrong width, or carries a
            status, kind, or timestamp that cannot be mapped.
    """
    _require_width(row, len(sql.NODE_COLUMNS), sql.TABLE_NODES)

    return Node(
        id=_text(row[0], sql.COL_NODE_ID),
        project_id=_text(row[1], sql.COL_NODE_PROJECT_ID),
        parent_id=_optional_text(row[2], sql.COL_NODE_PARENT_ID),
        kind=_vocabulary(row[3], NodeKind, sql.COL_NODE_KIND),
        status=_vocabulary(row[4], NodeStatus, sql.COL_NODE_STATUS),
        title=_text(row[5], sql.COL_NODE_TITLE),
        cf=CFReference(
            project=_optional_text(row[6], sql.COL_NODE_CF_PROJECT),
            phase=_optional_text(row[7], sql.COL_NODE_CF_PHASE),
            slice_name=_optional_text(row[8], sql.COL_NODE_CF_SLICE),
            artifact_path=_optional_text(row[9], sql.COL_NODE_CF_ARTIFACT_PATH),
        ),
        sq=SQReference(
            run_id=_optional_text(row[10], sql.COL_NODE_SQ_RUN_ID),
            review_artifact_path=_optional_text(
                row[11], sql.COL_NODE_SQ_REVIEW_ARTIFACT_PATH
            ),
            reviewed_sha=_optional_text(row[12], sql.COL_NODE_SQ_REVIEWED_SHA),
        ),
        created_at=_timestamp(row[13], sql.COL_NODE_CREATED_AT),
        updated_at=_timestamp(row[14], sql.COL_NODE_UPDATED_AT),
    )


def map_blocked_state(row: Sequence[object]) -> BlockedState:
    """Map one ``blocked_states`` row to a
    :class:`~amoeba.store.models.BlockedState`.

    The resolution slot is filled only when the row carries one; an unfilled
    slot maps to ``None``, which is the checkpoint.

    Raises:
        UnknownVocabularyValueError: If the row is the wrong width or carries an
            unmappable value.
    """
    _require_width(row, len(sql.BLOCKED_STATE_COLUMNS), sql.TABLE_BLOCKED_STATES)

    resolved_at = _timestamp(row[6], sql.COL_BLOCKED_RESOLVED_AT)
    resolved_by = _optional_text(row[4], sql.COL_BLOCKED_RESOLVED_BY)
    detail = _optional_text(row[5], sql.COL_BLOCKED_RESOLUTION_DETAIL)

    resolution: Resolution | None = None
    if resolved_at is not None or resolved_by is not None:
        if resolved_at is None or resolved_by is None or detail is None:
            raise UnknownVocabularyValueError(
                f"{sql.TABLE_BLOCKED_STATES} row has a partially-filled resolution slot"
            )
        resolution = Resolution(
            resolved_by=resolved_by, detail=detail, resolved_at=resolved_at
        )

    return BlockedState(
        id=_text(row[0], sql.COL_BLOCKED_ID),
        node_id=_text(row[1], sql.COL_BLOCKED_NODE_ID),
        kind=_vocabulary(row[2], BlockedKind, sql.COL_BLOCKED_KIND),
        context=_text(row[3], sql.COL_BLOCKED_CONTEXT),
        resolution=resolution,
        created_at=_timestamp(row[7], sql.COL_BLOCKED_CREATED_AT),
        updated_at=_timestamp(row[8], sql.COL_BLOCKED_UPDATED_AT),
    )
