"""SQL for questions held on a request (slice 242, D2, D3).

Every move out of ``waiting_on_request`` is a compare-and-set on that state, so a
concurrent ``answer``, ``dismiss`` or second ``handle_pause`` wins cleanly and the
loser learns it from the row count. State values are bound parameters (from
``QuestionState``), so no vocabulary is spelled here.
"""

from __future__ import annotations

from typing import Final

from amoeba.store.sql import QUESTION_COLUMNS

#: A lost race inserts nothing. Parameters: run id, paused_at, member, question,
#: checkout, held state, request id, claimed_at, updated_at, owner.
INSERT_HELD: Final = """
INSERT INTO questions (run_id, paused_at, member_id, question, checkout, state,
    request_id, claimed_at, updated_at, owner_id)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT (run_id, paused_at) DO NOTHING
"""
#: Every held row, oldest first. Parameter: the held state.
SELECT_HELD_ROWS: Final = (
    f"SELECT {QUESTION_COLUMNS} FROM questions WHERE state = ? "
    "ORDER BY claimed_at, rowid"
)
#: ``waiting_on_request -> claimed``; the claim's age starts now (D3). Parameters:
#: claimed state, answering run, passages, slice label, source commit, claimed_at,
#: updated_at, run id, paused_at, held state.
CLAIM_HELD: Final = """
UPDATE questions SET state = ?, answering_run_id = ?, passages = ?, slice_label = ?,
    source_commit = ?, claimed_at = ?, updated_at = ?
WHERE run_id = ? AND paused_at = ? AND state = ?
"""
#: ``waiting_on_request -> waiting_on_pm``; ``claimed_at`` stays the hold time.
#: Parameters: waiting state, reason, detail, updated_at, run id, paused_at, held
#: state.
SETTLE_HELD_WAITING: Final = """
UPDATE questions SET state = ?, waiting_reason = ?, waiting_detail = ?, updated_at = ?
WHERE run_id = ? AND paused_at = ? AND state = ?
"""
#: Leaves ``updated_at``, the close compare-and-set's guard. A compare-and-set on the
#: last start the caller read (``IS`` also matches null), so two callers that read the
#: row at once start it once. Parameters: now, run id, paused_at, held state, the
#: start_attempted_at read.
MARK_START_ATTEMPTED: Final = """
UPDATE questions SET start_attempted_at = ?
WHERE run_id = ? AND paused_at = ? AND state = ? AND start_attempted_at IS ?
"""
