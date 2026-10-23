"""Every SQL statement and column name for the Runner's tables.

Sibling of ``sql_inbox.py`` under the same rule: a name or statement for
``routing_table_versions``, ``routing_decisions``, ``attempt_counts`` or
``desired_states`` appears here and in migration ``009`` and nowhere else. The
five ``messages`` columns migration ``009`` added are defined in ``sql_inbox``
beside the other ``messages`` columns, and this module imports them.

Every value is a bound parameter, except where a partial index's own ``WHERE``
literal must be repeated for SQLite to use it; each such place says so.
"""

from __future__ import annotations

from typing import Final

# --------------------------------------------------------------------------
# routing_table_versions
# --------------------------------------------------------------------------

TABLE_ROUTING_TABLE_VERSIONS: Final = "routing_table_versions"

COL_TABLE_VERSION: Final = "version"
COL_TABLE_CONTENT: Final = "content"
COL_TABLE_FIRST_USED_AT: Final = "first_used_at"

#: Column order for every table-version SELECT and for row mapping.
TABLE_VERSION_COLUMNS: Final = (
    COL_TABLE_VERSION,
    COL_TABLE_CONTENT,
    COL_TABLE_FIRST_USED_AT,
)

# --------------------------------------------------------------------------
# routing_decisions
# --------------------------------------------------------------------------

TABLE_ROUTING_DECISIONS: Final = "routing_decisions"

COL_DECISION_ID: Final = "id"
COL_DECISION_PROJECT_ID: Final = "project_id"
COL_DECISION_NODE_ID: Final = "node_id"
COL_DECISION_JOURNAL_ENTRY_ID: Final = "journal_entry_id"
COL_DECISION_INPUTS: Final = "inputs"
COL_DECISION_RULE_ID: Final = "rule_id"
COL_DECISION_TABLE_VERSION: Final = "table_version"
COL_DECISION_AMOEBA_VERSION: Final = "amoeba_version"
COL_DECISION_ROUTE: Final = "route"
COL_DECISION_ROUTE_PARAMETERS: Final = "route_parameters"
COL_DECISION_ATTEMPT_STEP: Final = "attempt_step"
COL_DECISION_ATTEMPT_COUNT: Final = "attempt_count"
COL_DECISION_DECIDED_AT: Final = "decided_at"

#: Column order for every decision SELECT and for row mapping.
DECISION_COLUMNS: Final = (
    COL_DECISION_ID,
    COL_DECISION_PROJECT_ID,
    COL_DECISION_NODE_ID,
    COL_DECISION_JOURNAL_ENTRY_ID,
    COL_DECISION_INPUTS,
    COL_DECISION_RULE_ID,
    COL_DECISION_TABLE_VERSION,
    COL_DECISION_AMOEBA_VERSION,
    COL_DECISION_ROUTE,
    COL_DECISION_ROUTE_PARAMETERS,
    COL_DECISION_ATTEMPT_STEP,
    COL_DECISION_ATTEMPT_COUNT,
    COL_DECISION_DECIDED_AT,
)

INDEX_DECISIONS_ENTRY: Final = "idx_routing_decisions_entry"
INDEX_DECISIONS_NODE: Final = "idx_routing_decisions_node"

# --------------------------------------------------------------------------
# attempt_counts
# --------------------------------------------------------------------------

TABLE_ATTEMPT_COUNTS: Final = "attempt_counts"

COL_ATTEMPT_NODE_ID: Final = "node_id"
COL_ATTEMPT_STEP: Final = "step"
COL_ATTEMPT_COUNT: Final = "count"
COL_ATTEMPT_UPDATED_AT: Final = "updated_at"

#: Column order for the attempt-count table.
ATTEMPT_COLUMNS: Final = (
    COL_ATTEMPT_NODE_ID,
    COL_ATTEMPT_STEP,
    COL_ATTEMPT_COUNT,
    COL_ATTEMPT_UPDATED_AT,
)

# --------------------------------------------------------------------------
# desired_states
# --------------------------------------------------------------------------

TABLE_DESIRED_STATES: Final = "desired_states"

COL_DESIRED_ID: Final = "id"
COL_DESIRED_PROJECT_ID: Final = "project_id"
COL_DESIRED_NODE_ID: Final = "node_id"
COL_DESIRED_DRIVE: Final = "drive"
COL_DESIRED_DRIVE_UNTIL_STEP: Final = "drive_until_step"
COL_DESIRED_HOLD: Final = "hold"
COL_DESIRED_MESSAGE_ID: Final = "message_id"
COL_DESIRED_UPDATED_AT: Final = "updated_at"

#: Column order for every desired-state SELECT and for row mapping.
DESIRED_STATE_COLUMNS: Final = (
    COL_DESIRED_ID,
    COL_DESIRED_PROJECT_ID,
    COL_DESIRED_NODE_ID,
    COL_DESIRED_DRIVE,
    COL_DESIRED_DRIVE_UNTIL_STEP,
    COL_DESIRED_HOLD,
    COL_DESIRED_MESSAGE_ID,
    COL_DESIRED_UPDATED_AT,
)

INDEX_DESIRED_PROJECT_TARGET: Final = "idx_desired_states_project_target"
INDEX_DESIRED_NODE_TARGET: Final = "idx_desired_states_node_target"

# A target is one project or one node. SQLite cannot bind ``node_id IS NULL``,
# so the project target and a node target are separate statements. Each repeats
# its partial unique index's WHERE literally, so the lookup uses the index.
_DESIRED_SELECT_LIST = ", ".join(DESIRED_STATE_COLUMNS)

SELECT_DESIRED_PROJECT_TARGET: Final = f"""
SELECT {_DESIRED_SELECT_LIST}
FROM {TABLE_DESIRED_STATES}
WHERE {COL_DESIRED_PROJECT_ID} = ?
  AND {COL_DESIRED_NODE_ID} IS NULL
"""

SELECT_DESIRED_NODE_TARGET: Final = f"""
SELECT {_DESIRED_SELECT_LIST}
FROM {TABLE_DESIRED_STATES}
WHERE {COL_DESIRED_NODE_ID} IS NOT NULL
  AND {COL_DESIRED_NODE_ID} = ?
"""

#: Project target first (its node id is NULL), then by node id.
SELECT_DESIRED_FOR_PROJECT: Final = f"""
SELECT {_DESIRED_SELECT_LIST}
FROM {TABLE_DESIRED_STATES}
WHERE {COL_DESIRED_PROJECT_ID} = ?
ORDER BY {COL_DESIRED_NODE_ID} IS NOT NULL, {COL_DESIRED_NODE_ID}
"""

#: Replacing a target's row is delete-then-insert in one transaction, because an
#: ``ON CONFLICT`` target cannot name a partial index's predicate portably.
DELETE_DESIRED_PROJECT_TARGET: Final = f"""
DELETE FROM {TABLE_DESIRED_STATES}
WHERE {COL_DESIRED_PROJECT_ID} = ?
  AND {COL_DESIRED_NODE_ID} IS NULL
"""

DELETE_DESIRED_NODE_TARGET: Final = f"""
DELETE FROM {TABLE_DESIRED_STATES}
WHERE {COL_DESIRED_NODE_ID} IS NOT NULL
  AND {COL_DESIRED_NODE_ID} = ?
"""

INSERT_DESIRED_STATE: Final = f"""
INSERT INTO {TABLE_DESIRED_STATES} ({_DESIRED_SELECT_LIST})
VALUES (?, ?, ?, ?, ?, ?, ?, ?)
"""
