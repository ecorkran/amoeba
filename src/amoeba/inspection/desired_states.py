"""Rows for the ``desired-states`` listing: what the PM has asked the Runner to do.

Reads only the store's desired-state rows. It does not import the Runner: the
listing shows what is stored, and what a row means is the Runner's rule to apply.
"""

from __future__ import annotations

from typing import Final

from amoeba.inspection.listing import ListingRequest, Row
from amoeba.store import Store

#: The ``target`` shown for the project-level row, which has no node.
PROJECT_TARGET: Final = "project"

COLUMN_TARGET: Final = "target"
COLUMN_DRIVE: Final = "drive"
COLUMN_UNTIL: Final = "until"
COLUMN_HOLD: Final = "hold"
COLUMN_MESSAGE_ID: Final = "message_id"
COLUMN_UPDATED_AT: Final = "updated_at"

DESIRED_STATE_COLUMNS: Final = (
    COLUMN_TARGET,
    COLUMN_DRIVE,
    COLUMN_UNTIL,
    COLUMN_HOLD,
    COLUMN_MESSAGE_ID,
    COLUMN_UPDATED_AT,
)


def _flag(value: bool | None) -> str:
    """A nullable flag as text; unset is the empty string."""
    return "" if value is None else str(value).lower()


def desired_state_rows(store: Store, request: ListingRequest) -> list[Row]:
    """A project's desired-state rows: the project target first, then by node id."""
    return [
        {
            COLUMN_TARGET: PROJECT_TARGET if row.node_id is None else row.node_id,
            COLUMN_DRIVE: _flag(row.drive),
            COLUMN_UNTIL: row.drive_until_step or "",
            COLUMN_HOLD: _flag(row.hold),
            COLUMN_MESSAGE_ID: row.message_id,
            COLUMN_UPDATED_AT: row.updated_at.isoformat(),
        }
        for row in store.desired_states(request.require_project_id())
    ]
