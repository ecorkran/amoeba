"""SQL that finds questions by their machine, and the opener's one backfill (slice 262).

Statements only. A question's machine is the one whose files its run needs (D14); a
row with no machine is never work for any machine.
"""

from __future__ import annotations

from typing import Final

from amoeba.store.sql import OPEN_QUESTION_CLAUSE, QUESTION_COLUMNS

#: The open questions on one machine, oldest first. Parameters: machine id, then the
#: open clause's five (claimed, waiting_on_pm, waiting_on_request, answered, refused).
SELECT_OPEN_QUESTIONS_OF_MACHINE: Final = (
    f"SELECT {QUESTION_COLUMNS} FROM questions WHERE questions.machine_id = ? "
    f"AND {OPEN_QUESTION_CLAUSE} ORDER BY questions.claimed_at, questions.rowid"
)
#: The open questions of one run on one machine, oldest first (the pause sweep judges
#: only the calling machine's rows). Parameters: run id, machine id, then the open
#: clause's five.
SELECT_OPEN_ROWS_OF_RUN_ON_MACHINE: Final = (
    f"SELECT {QUESTION_COLUMNS} FROM questions WHERE questions.run_id = ? "
    f"AND questions.machine_id = ? AND {OPEN_QUESTION_CLAUSE} "
    "ORDER BY questions.claimed_at, questions.rowid"
)
#: The name of a question's machine, or no row when it has none. Parameters: run id,
#: paused_at.
SELECT_QUESTION_MACHINE_NAME: Final = (
    "SELECT machines.name FROM questions "
    "JOIN machines ON machines.machine_id = questions.machine_id "
    "WHERE questions.run_id = ? AND questions.paused_at = ?"
)
#: A question's machine id, name and when it last called the hub. The id is null and
#: the name and time null after ``rm-machine``. Parameters: run id, paused_at.
SELECT_QUESTION_MACHINE: Final = (
    "SELECT questions.machine_id, machines.name, machines.last_called_at "
    "FROM questions LEFT JOIN machines ON machines.machine_id = questions.machine_id "
    "WHERE questions.run_id = ? AND questions.paused_at = ?"
)
#: One row of either table with no machine, for the opener's check (D14).
SELECT_ROW_WITHOUT_MACHINE: Final = (
    "SELECT EXISTS (SELECT 1 FROM questions WHERE machine_id IS NULL) "
    "OR EXISTS (SELECT 1 FROM wakes WHERE machine_id IS NULL)"
)
#: Parameter: the machine id. Each updates only rows with no machine.
SET_QUESTIONS_MACHINE: Final = (
    "UPDATE questions SET machine_id = ? WHERE machine_id IS NULL"
)
SET_WAKES_MACHINE: Final = "UPDATE wakes SET machine_id = ? WHERE machine_id IS NULL"

# --- the resume claim (D6) --------------------------------------------------

#: The one statement that takes a resume claim: the outcome is not final (null or
#: refused) and the claim is free or older than the limit. Parameters: now, the new
#: claim id, seq, refused, the oldest ``resume_started_at`` that still holds a claim
#: (inclusive: a claim as old as the limit is taken).
CLAIM_RESUME: Final = """
UPDATE answers SET resume_started_at = ?, resume_claim_id = ?
WHERE seq = ?
    AND (resume_outcome IS NULL OR resume_outcome = ?)
    AND (resume_claim_id IS NULL OR resume_started_at <= ?)
"""
