"""Mapping between the Runner's table rows and their records.

Follows ``mapping_inbox.py``: rows arrive positionally in the column order
declared by ``sql_runner``, and a row that cannot be mapped raises rather than
yielding a partially-populated object.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from amoeba.store import sql_runner
from amoeba.store.mapping_journal import decode_mapping, decode_timestamp
from amoeba.store.models import UnknownVocabularyValueError
from amoeba.store.row_values import integer, optional_text, text
from amoeba.store.runner_models import (
    DesiredState,
    Route,
    RoutingDecision,
    RoutingTableVersion,
)


def _require_width(row: Sequence[object], columns: tuple[str, ...], table: str) -> None:
    if len(row) != len(columns):
        raise UnknownVocabularyValueError(
            f"{table} row has {len(row)} columns, expected {len(columns)}"
        )


def _required_timestamp(value: object, column: str) -> datetime:
    decoded = decode_timestamp(value, column)
    if decoded is None:
        raise UnknownVocabularyValueError(f"{column} is NULL")
    return decoded


def _optional_bool(value: object, column: str) -> bool | None:
    """Read a nullable boolean stored as ``0``, ``1`` or ``NULL``."""
    if value is None:
        return None
    if value not in (0, 1):
        raise UnknownVocabularyValueError(f"{column} is not 0, 1 or NULL: {value!r}")
    return value == 1


def _route(value: object) -> Route:
    column = sql_runner.COL_DECISION_ROUTE
    try:
        return Route(text(value, column))
    except ValueError as error:
        # Specific: the stored string is outside the vocabulary. Re-raised so
        # the caller never receives a defaulted decision.
        raise UnknownVocabularyValueError(
            f"{column} value {value!r} is not a valid Route"
        ) from error


def map_table_version(row: Sequence[object]) -> RoutingTableVersion:
    """Map one ``routing_table_versions`` row.

    Raises:
        UnknownVocabularyValueError: If the row is the wrong width or carries a
            value that cannot be mapped.
    """
    _require_width(
        row, sql_runner.TABLE_VERSION_COLUMNS, sql_runner.TABLE_ROUTING_TABLE_VERSIONS
    )
    return RoutingTableVersion(
        version=text(row[0], sql_runner.COL_TABLE_VERSION),
        content=text(row[1], sql_runner.COL_TABLE_CONTENT),
        first_used_at=_required_timestamp(row[2], sql_runner.COL_TABLE_FIRST_USED_AT),
    )


def map_routing_decision(row: Sequence[object]) -> RoutingDecision:
    """Map one ``routing_decisions`` row.

    Raises:
        UnknownVocabularyValueError: If the row is the wrong width or carries a
            value that cannot be mapped, including a route outside ``Route``.
    """
    _require_width(row, sql_runner.DECISION_COLUMNS, sql_runner.TABLE_ROUTING_DECISIONS)
    return RoutingDecision(
        id=text(row[0], sql_runner.COL_DECISION_ID),
        project_id=text(row[1], sql_runner.COL_DECISION_PROJECT_ID),
        node_id=text(row[2], sql_runner.COL_DECISION_NODE_ID),
        journal_entry_id=optional_text(
            row[3], sql_runner.COL_DECISION_JOURNAL_ENTRY_ID
        ),
        inputs=decode_mapping(row[4], sql_runner.COL_DECISION_INPUTS),
        rule_id=text(row[5], sql_runner.COL_DECISION_RULE_ID),
        table_version=text(row[6], sql_runner.COL_DECISION_TABLE_VERSION),
        amoeba_version=text(row[7], sql_runner.COL_DECISION_AMOEBA_VERSION),
        route=_route(row[8]),
        route_parameters=decode_mapping(
            row[9], sql_runner.COL_DECISION_ROUTE_PARAMETERS
        ),
        attempt_step=optional_text(row[10], sql_runner.COL_DECISION_ATTEMPT_STEP),
        attempt_count=(
            None
            if row[11] is None
            else integer(row[11], sql_runner.COL_DECISION_ATTEMPT_COUNT)
        ),
        decided_at=_required_timestamp(row[12], sql_runner.COL_DECISION_DECIDED_AT),
    )


def map_desired_state(row: Sequence[object]) -> DesiredState:
    """Map one ``desired_states`` row.

    Raises:
        UnknownVocabularyValueError: If the row is the wrong width or carries a
            value that cannot be mapped.
    """
    _require_width(
        row, sql_runner.DESIRED_STATE_COLUMNS, sql_runner.TABLE_DESIRED_STATES
    )
    return DesiredState(
        id=text(row[0], sql_runner.COL_DESIRED_ID),
        project_id=text(row[1], sql_runner.COL_DESIRED_PROJECT_ID),
        node_id=optional_text(row[2], sql_runner.COL_DESIRED_NODE_ID),
        drive=_optional_bool(row[3], sql_runner.COL_DESIRED_DRIVE),
        drive_until_step=optional_text(row[4], sql_runner.COL_DESIRED_DRIVE_UNTIL_STEP),
        hold=_optional_bool(row[5], sql_runner.COL_DESIRED_HOLD),
        message_id=text(row[6], sql_runner.COL_DESIRED_MESSAGE_ID),
        updated_at=_required_timestamp(row[7], sql_runner.COL_DESIRED_UPDATED_AT),
    )
