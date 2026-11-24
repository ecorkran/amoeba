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

# --- what a machine has waiting (262 D10) ----------------------------------------

#: The latest answers of ``answered`` questions on a machine with no outcome that
#: ``claim_resume`` would take: no claim, or a claim at least as old as the limit.
#: Unlike ``CLAIM_RESUME`` it leaves out ``refused``: a refused resume is not pending
#: work, and is tried again only by a new ``answer`` or ``handle-pause`` (D6, D10).
#: Oldest first. Parameters: machine id, the answered state, the oldest
#: ``resume_started_at`` that still holds a claim (inclusive).
SELECT_RESUME_WORK: Final = """
SELECT answers.seq, answers.run_id, answers.resume_start_count FROM answers
JOIN questions ON questions.run_id = answers.run_id
    AND questions.paused_at = answers.paused_at
WHERE questions.machine_id = ? AND questions.state = ?
    AND answers.resume_outcome IS NULL
    AND answers.seq = (
        SELECT MAX(any_answer.seq) FROM answers AS any_answer
        WHERE any_answer.run_id = answers.run_id
            AND any_answer.paused_at = answers.paused_at)
    AND (answers.resume_claim_id IS NULL OR answers.resume_started_at <= ?)
ORDER BY answers.seq
"""
#: Held rows on a machine whose request has ended or is no longer stored, with no start
#: in the last ``answering_wait_seconds``. Never-started first, then the oldest start.
#: Parameters: machine id, the held state, the newest ``start_attempted_at`` that
#: allows a start (inclusive), then the four terminal request states, the open state
#: and now (an open request at or past its expiry has ended). A request no longer
#: stored (pruned) counts as ended, as 242 made it: its ``handle-pause`` waits on the
#: PM as ``request_unknown``. A row that names a note,
#: which has no state, is due too: its ``handle-pause`` reports the corrupt row, and
#: the cap ends it.
SELECT_HELD_WORK: Final = f"""
SELECT {QUESTION_COLUMNS} FROM questions
WHERE machine_id = ? AND state = ?
    AND (start_attempted_at IS NULL OR start_attempted_at <= ?)
    AND (
        NOT EXISTS (
            SELECT 1 FROM messages WHERE messages.message_id = questions.request_id)
        OR EXISTS (
            SELECT 1 FROM messages WHERE messages.message_id = questions.request_id
                AND (messages.state IS NULL OR messages.state IN (?, ?, ?, ?)
                    OR (messages.state = ? AND messages.expires_at <= ?))))
ORDER BY start_attempted_at IS NOT NULL, COALESCE(start_attempted_at, claimed_at), rowid
"""
#: Claimed rows on a machine whose claim is dead and with no start in the last
#: ``answering_wait_seconds``. Parameters: machine id, the claimed state, the newest
#: ``updated_at`` that counts as dead (inclusive), the newest ``start_attempted_at``
#: that allows a start (inclusive).
SELECT_DEAD_CLAIM_WORK: Final = f"""
SELECT {QUESTION_COLUMNS} FROM questions
WHERE machine_id = ? AND state = ? AND updated_at <= ?
    AND (start_attempted_at IS NULL OR start_attempted_at <= ?)
ORDER BY start_attempted_at IS NOT NULL, COALESCE(start_attempted_at, claimed_at), rowid
"""
#: Members with an open, unexpired request that carries a wake mark, and a checkout on
#: a machine that has a wake command: the candidates for a wake due on that machine.
#: Parameters: machine id, the open state, now.
SELECT_WAKE_CANDIDATES: Final = """
SELECT DISTINCT messages.to_member FROM messages
JOIN checkouts ON checkouts.member_id = messages.to_member
    AND checkouts.machine_id = ? AND checkouts.wake_command IS NOT NULL
WHERE messages.kind = 'request' AND messages.state = ? AND messages.expires_at > ?
    AND messages.wake_wanted_at IS NOT NULL
ORDER BY messages.to_member
"""
#: One more automatic resume handed out for the answer. Parameter: seq.
COUNT_RESUME_START: Final = (
    "UPDATE answers SET resume_start_count = resume_start_count + 1 WHERE seq = ?"
)

# --- rm-machine (D13) ---------------------------------------------------------

#: Parameter: answer seq.
CLEAR_RESUME_CLAIM: Final = "UPDATE answers SET resume_claim_id = NULL WHERE seq = ?"
#: Parameters: ended_at, outcome, detail, machine id.
END_WAKES_OF_MACHINE: Final = (
    "UPDATE wakes SET ended_at = ?, outcome = ?, detail = ? "
    "WHERE machine_id = ? AND ended_at IS NULL"
)
#: Parameter: machine id. The rows stay as history with no machine.
RELEASE_QUESTIONS_OF_MACHINE: Final = (
    "UPDATE questions SET machine_id = NULL WHERE machine_id = ?"
)
RELEASE_WAKES_OF_MACHINE: Final = (
    "UPDATE wakes SET machine_id = NULL, log_stem = NULL WHERE machine_id = ?"
)
