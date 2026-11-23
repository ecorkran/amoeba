"""SQL for standing answers (slice 230, D1 to D5, D8).

Every statement is composed from this module's constants only, and every value binds
with ``?``. ``ACTIVE`` is the one rule for a standing answer that still holds.
"""

from __future__ import annotations

from typing import Final

#: A row that has not been withdrawn.
ACTIVE: Final = "withdrawn_at IS NULL"

#: Select order: ``store.standing._row`` reads these positionally.
_STANDING_COLUMNS: Final = (
    "id, text, reach, program_id, member_id, given_at, withdrawn_at, withdraw_reason"
)
_SELECT_STANDING: Final = f"SELECT {_STANDING_COLUMNS} FROM standing_answers"

#: Parameters: text, reach, program id, member id, given at, owner.
INSERT_STANDING: Final = (
    "INSERT INTO standing_answers (text, reach, program_id, member_id, given_at, "
    "owner_id) VALUES (?, ?, ?, ?, ?, ?)"
)
#: The active row with the same text and reach (D2's safe repeat). ``IS`` matches a
#: null program or member. Parameters: text, reach, program id, member id.
SELECT_ACTIVE_MATCH: Final = (
    f"SELECT id FROM standing_answers WHERE {ACTIVE} AND text = ? AND reach = ? "
    "AND program_id IS ? AND member_id IS ?"
)
#: Parameter: id.
SELECT_WITHDRAWN_AT: Final = "SELECT withdrawn_at FROM standing_answers WHERE id = ?"
#: Compare-and-set: only an active row is withdrawn. Parameters: now, reason, id.
WITHDRAW_STANDING: Final = (
    "UPDATE standing_answers SET withdrawn_at = ?, withdraw_reason = ? "
    f"WHERE id = ? AND {ACTIVE}"
)
_NEWEST_FIRST: Final = "ORDER BY given_at DESC, id DESC"
SELECT_ACTIVE_STANDING: Final = f"{_SELECT_STANDING} WHERE {ACTIVE} {_NEWEST_FIRST}"
SELECT_ALL_STANDING: Final = f"{_SELECT_STANDING} {_NEWEST_FIRST}"
#: Active rows reaching one member (D5); never reads ``members``. Parameters: reach
#: ``all``; reach ``program``, the member's program id; reach ``member``, the
#: member's project id.
SELECT_STANDING_REACHING: Final = (
    f"{_SELECT_STANDING} WHERE {ACTIVE} AND (reach = ? "
    "OR (reach = ? AND program_id = ?) OR (reach = ? AND member_id = ?)) ORDER BY id"
)
#: Withdraws a member's active member-reach rows (D8). Parameters: now, reason,
#: reach ``member``, member id.
WITHDRAW_MEMBER_STANDING: Final = (
    "UPDATE standing_answers SET withdrawn_at = ?, withdraw_reason = ? "
    f"WHERE reach = ? AND member_id = ? AND {ACTIVE}"
)
