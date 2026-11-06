"""SQL for the program store: table and column names, and every statement.

The one definition site for the program store's names, as ``sql.py`` is for the
project store. Column order in each ``*_COLUMNS`` tuple is the order rows arrive
in, which ``mapping_program`` reads positionally. Names here must match
``program_schema/001_program_record.sql``.
"""

from __future__ import annotations

from typing import Final

TABLE_PROGRAMS: Final = "programs"
TABLE_PROGRAM_MEMBERS: Final = "program_members"
TABLE_CONSUMPTION_OVERRIDES: Final = "consumption_overrides"
TABLE_PROGRAM_SUBMISSIONS: Final = "program_submissions"

#: Every table the program store may hold, ``schema_meta`` included (the
#: locality rule's allowed set).
PROGRAM_STORE_TABLES: Final = frozenset(
    {
        "schema_meta",
        TABLE_PROGRAMS,
        TABLE_PROGRAM_MEMBERS,
        TABLE_CONSUMPTION_OVERRIDES,
        TABLE_PROGRAM_SUBMISSIONS,
    }
)

PROGRAM_COLUMNS: Final = (
    "program_id",
    "concept_member",
    "concept_path",
    "registered_at",
    "updated_at",
)
MEMBER_COLUMNS: Final = (
    "program_id",
    "project_id",
    "requests_initiative",
    "consumed",
    "registered_at",
    "updated_at",
)
OVERRIDE_COLUMNS: Final = ("program_id", "provider_id", "dependent_id", "consumed")
SUBMISSION_COLUMNS: Final = (
    "applied_seq",
    "id",
    "kind",
    "submitted_by",
    "submitted_at",
    "payload",
    "outcome",
    "reason",
    "applied_at",
)

_PROGRAM_LIST: Final = ", ".join(PROGRAM_COLUMNS)
_MEMBER_LIST: Final = ", ".join(MEMBER_COLUMNS)
_OVERRIDE_LIST: Final = ", ".join(OVERRIDE_COLUMNS)
_SUBMISSION_LIST: Final = ", ".join(SUBMISSION_COLUMNS)

SELECT_PROGRAMS: Final = f"""
SELECT {_PROGRAM_LIST}
FROM {TABLE_PROGRAMS}
ORDER BY program_id
"""

SELECT_PROGRAM_BY_ID: Final = f"""
SELECT {_PROGRAM_LIST}
FROM {TABLE_PROGRAMS}
WHERE program_id = ?
"""

SELECT_PROGRAM_OF_PROJECT: Final = f"""
SELECT {", ".join(f"prog.{column}" for column in PROGRAM_COLUMNS)}
FROM {TABLE_PROGRAMS} AS prog
JOIN {TABLE_PROGRAM_MEMBERS} AS member ON member.program_id = prog.program_id
WHERE member.project_id = ?
"""

SELECT_MEMBERS: Final = f"""
SELECT {_MEMBER_LIST}
FROM {TABLE_PROGRAM_MEMBERS}
WHERE program_id = ?
ORDER BY project_id
"""

SELECT_OVERRIDES: Final = f"""
SELECT {_OVERRIDE_LIST}
FROM {TABLE_CONSUMPTION_OVERRIDES}
WHERE program_id = ?
ORDER BY provider_id, dependent_id
"""

SELECT_SUBMISSION_BY_ID: Final = f"""
SELECT {_SUBMISSION_LIST}
FROM {TABLE_PROGRAM_SUBMISSIONS}
WHERE id = ?
"""

SELECT_SUBMISSIONS: Final = f"""
SELECT {_SUBMISSION_LIST}
FROM {TABLE_PROGRAM_SUBMISSIONS}
ORDER BY applied_seq
"""

# --------------------------------------------------------------------------
# Writes. Every statement runs inside ``apply_submission``'s one transaction.
# --------------------------------------------------------------------------

INSERT_PROGRAM: Final = f"""
INSERT INTO {TABLE_PROGRAMS} ({_PROGRAM_LIST})
VALUES (?, ?, ?, ?, ?)
"""

#: Replaces the concept location and moves ``updated_at``; ``registered_at``
#: never changes.
UPDATE_PROGRAM: Final = f"""
UPDATE {TABLE_PROGRAMS}
SET concept_member = ?, concept_path = ?, updated_at = ?
WHERE program_id = ?
"""

TOUCH_PROGRAM: Final = f"""
UPDATE {TABLE_PROGRAMS}
SET updated_at = ?
WHERE program_id = ?
"""

INSERT_MEMBER: Final = f"""
INSERT INTO {TABLE_PROGRAM_MEMBERS} ({_MEMBER_LIST})
VALUES (?, ?, ?, ?, ?, ?)
"""

UPDATE_MEMBER: Final = f"""
UPDATE {TABLE_PROGRAM_MEMBERS}
SET requests_initiative = ?, consumed = ?, updated_at = ?
WHERE program_id = ? AND project_id = ?
"""

DELETE_MEMBER: Final = f"""
DELETE FROM {TABLE_PROGRAM_MEMBERS}
WHERE program_id = ? AND project_id = ?
"""

INSERT_OVERRIDE: Final = f"""
INSERT INTO {TABLE_CONSUMPTION_OVERRIDES} ({_OVERRIDE_LIST})
VALUES (?, ?, ?, ?)
"""

DELETE_OVERRIDES_OF_PROVIDER: Final = f"""
DELETE FROM {TABLE_CONSUMPTION_OVERRIDES}
WHERE program_id = ? AND provider_id = ?
"""

#: ``applied_seq`` is the next integer, assigned inside the write transaction so
#: it is the receiver's order and never repeats.
INSERT_SUBMISSION: Final = f"""
INSERT INTO {TABLE_PROGRAM_SUBMISSIONS} (
    id, kind, submitted_by, submitted_at, payload, outcome, reason, applied_at,
    applied_seq
)
SELECT ?, ?, ?, ?, ?, ?, ?, ?, COALESCE(MAX(applied_seq), 0) + 1
FROM {TABLE_PROGRAM_SUBMISSIONS}
"""
