"""Every SQL statement and column name used by verdicts and finding observations.

Sibling of ``sql.py`` and ``sql_inbox.py``, under the same rule: a column name or
statement for ``verdicts`` or ``finding_observations`` appears here and in
migration ``005`` and nowhere else. Every value is a bound parameter.
"""

from __future__ import annotations

from typing import Final

TABLE_VERDICTS: Final = "verdicts"
TABLE_FINDING_OBSERVATIONS: Final = "finding_observations"

# --------------------------------------------------------------------------
# verdicts columns — the single definition site
# --------------------------------------------------------------------------

COL_VERDICT_RECORDED_SEQ: Final = "recorded_seq"
COL_VERDICT_ID: Final = "id"
COL_VERDICT_PROJECT_ID: Final = "project_id"
COL_VERDICT_NODE_ID: Final = "node_id"
COL_VERDICT_JOURNAL_ENTRY_ID: Final = "journal_entry_id"
COL_VERDICT_VERDICT: Final = "verdict"
COL_VERDICT_DERIVATION: Final = "derivation"
COL_VERDICT_FALLBACK_USED: Final = "fallback_used"
COL_VERDICT_FINDINGS_PARSED: Final = "findings_parsed"
COL_VERDICT_DIFF_TRUNCATED: Final = "diff_truncated"
COL_VERDICT_PROVIDER_FAILURE: Final = "provider_failure"
COL_VERDICT_REVIEW_TYPE: Final = "review_type"
COL_VERDICT_MODEL: Final = "model"
COL_VERDICT_REQUESTED_MODEL: Final = "requested_model"
COL_VERDICT_REVIEWED_SHA: Final = "reviewed_sha"
COL_VERDICT_SCORE: Final = "score"
COL_VERDICT_CRITERIA: Final = "criteria"
COL_VERDICT_TOOL_CALLS_MADE: Final = "tool_calls_made"
COL_VERDICT_SQ_RUN_ID: Final = "sq_run_id"
COL_VERDICT_UPSTREAM: Final = "upstream"
COL_VERDICT_UPSTREAM_VERSION: Final = "upstream_version"
COL_VERDICT_SOURCE: Final = "source"
COL_VERDICT_SOURCE_PATH: Final = "source_path"
COL_VERDICT_RECORDED_AT: Final = "recorded_at"

#: Column order for every verdict SELECT and for row mapping.
VERDICT_COLUMNS: Final = (
    COL_VERDICT_RECORDED_SEQ,
    COL_VERDICT_ID,
    COL_VERDICT_PROJECT_ID,
    COL_VERDICT_NODE_ID,
    COL_VERDICT_JOURNAL_ENTRY_ID,
    COL_VERDICT_VERDICT,
    COL_VERDICT_DERIVATION,
    COL_VERDICT_FALLBACK_USED,
    COL_VERDICT_FINDINGS_PARSED,
    COL_VERDICT_DIFF_TRUNCATED,
    COL_VERDICT_PROVIDER_FAILURE,
    COL_VERDICT_REVIEW_TYPE,
    COL_VERDICT_MODEL,
    COL_VERDICT_REQUESTED_MODEL,
    COL_VERDICT_REVIEWED_SHA,
    COL_VERDICT_SCORE,
    COL_VERDICT_CRITERIA,
    COL_VERDICT_TOOL_CALLS_MADE,
    COL_VERDICT_SQ_RUN_ID,
    COL_VERDICT_UPSTREAM,
    COL_VERDICT_UPSTREAM_VERSION,
    COL_VERDICT_SOURCE,
    COL_VERDICT_SOURCE_PATH,
    COL_VERDICT_RECORDED_AT,
)

#: ``recorded_seq`` is omitted from inserts so SQLite assigns arrival order.
VERDICT_INSERT_COLUMNS: Final = VERDICT_COLUMNS[1:]

# --------------------------------------------------------------------------
# finding_observations columns — the single definition site
# --------------------------------------------------------------------------

COL_OBSERVATION_VERDICT_ID: Final = "verdict_id"
COL_OBSERVATION_ORDINAL: Final = "ordinal"
COL_OBSERVATION_POSITION_ID: Final = "position_id"
COL_OBSERVATION_SEVERITY: Final = "severity"
COL_OBSERVATION_CATEGORY: Final = "category"
COL_OBSERVATION_SUMMARY: Final = "summary"
COL_OBSERVATION_LOCATION: Final = "location"
COL_OBSERVATION_NORMALIZED_LOCATION: Final = "normalized_location"
COL_OBSERVATION_NORMALIZED_SUMMARY: Final = "normalized_summary"
COL_OBSERVATION_IDENTITY: Final = "identity"
COL_OBSERVATION_IDENTITY_VERSION: Final = "identity_version"

#: Column order for every observation SELECT, for inserts, and for row mapping.
OBSERVATION_COLUMNS: Final = (
    COL_OBSERVATION_VERDICT_ID,
    COL_OBSERVATION_ORDINAL,
    COL_OBSERVATION_POSITION_ID,
    COL_OBSERVATION_SEVERITY,
    COL_OBSERVATION_CATEGORY,
    COL_OBSERVATION_SUMMARY,
    COL_OBSERVATION_LOCATION,
    COL_OBSERVATION_NORMALIZED_LOCATION,
    COL_OBSERVATION_NORMALIZED_SUMMARY,
    COL_OBSERVATION_IDENTITY,
    COL_OBSERVATION_IDENTITY_VERSION,
)

#: Index names, so the migration test asserts against constants.
INDEX_VERDICTS_PREVIOUS_ROUND: Final = "idx_verdicts_previous_round"
INDEX_FINDING_OBSERVATIONS_IDENTITY: Final = "idx_finding_observations_identity"


def _qualified(table: str, columns: tuple[str, ...]) -> str:
    return ", ".join(f"{table}.{column}" for column in columns)


def _placeholders(count: int) -> str:
    return ", ".join("?" for _ in range(count))


_VERDICT_SELECT_LIST: Final = _qualified(TABLE_VERDICTS, VERDICT_COLUMNS)
_OBSERVATION_SELECT_LIST: Final = _qualified(
    TABLE_FINDING_OBSERVATIONS, OBSERVATION_COLUMNS
)

# --------------------------------------------------------------------------
# verdicts statements
# --------------------------------------------------------------------------

INSERT_VERDICT: Final = f"""
INSERT INTO {TABLE_VERDICTS} ({", ".join(VERDICT_INSERT_COLUMNS)})
VALUES ({_placeholders(len(VERDICT_INSERT_COLUMNS))})
"""

SELECT_VERDICT_BY_ID: Final = f"""
SELECT {_VERDICT_SELECT_LIST}
FROM {TABLE_VERDICTS}
WHERE {COL_VERDICT_ID} = ?
"""

SELECT_VERDICTS: Final = f"""
SELECT {_VERDICT_SELECT_LIST}
FROM {TABLE_VERDICTS}
WHERE {COL_VERDICT_PROJECT_ID} = ?
ORDER BY {COL_VERDICT_RECORDED_SEQ}
"""

SELECT_VERDICTS_FOR_NODE: Final = f"""
SELECT {_VERDICT_SELECT_LIST}
FROM {TABLE_VERDICTS}
WHERE {COL_VERDICT_PROJECT_ID} = ?
  AND {COL_VERDICT_NODE_ID} = ?
ORDER BY {COL_VERDICT_RECORDED_SEQ}
"""

#: Earlier rounds of one node's reviews of one type, newest first. The caller
#: takes the first comparable one: the trust label is computed, not stored.
SELECT_EARLIER_ROUNDS: Final = f"""
SELECT {_VERDICT_SELECT_LIST}
FROM {TABLE_VERDICTS}
WHERE {COL_VERDICT_PROJECT_ID} = ?
  AND {COL_VERDICT_NODE_ID} = ?
  AND {COL_VERDICT_REVIEW_TYPE} = ?
  AND {COL_VERDICT_RECORDED_SEQ} < ?
ORDER BY {COL_VERDICT_RECORDED_SEQ} DESC
"""

# --------------------------------------------------------------------------
# finding_observations statements
# --------------------------------------------------------------------------

INSERT_OBSERVATION: Final = f"""
INSERT INTO {TABLE_FINDING_OBSERVATIONS} ({", ".join(OBSERVATION_COLUMNS)})
VALUES ({_placeholders(len(OBSERVATION_COLUMNS))})
"""

SELECT_OBSERVATIONS: Final = f"""
SELECT {_OBSERVATION_SELECT_LIST}
FROM {TABLE_FINDING_OBSERVATIONS}
WHERE {COL_OBSERVATION_VERDICT_ID} = ?
ORDER BY {COL_OBSERVATION_ORDINAL}
"""

_OBSERVATIONS_WITH_NODE: Final = f"""
SELECT {TABLE_VERDICTS}.{COL_VERDICT_NODE_ID}, {_OBSERVATION_SELECT_LIST}
FROM {TABLE_FINDING_OBSERVATIONS}
JOIN {TABLE_VERDICTS}
  ON {TABLE_VERDICTS}.{COL_VERDICT_ID}
   = {TABLE_FINDING_OBSERVATIONS}.{COL_OBSERVATION_VERDICT_ID}
WHERE {TABLE_VERDICTS}.{COL_VERDICT_PROJECT_ID} = ?
"""

_ARRIVAL_ORDER: Final = f"""
ORDER BY {TABLE_VERDICTS}.{COL_VERDICT_RECORDED_SEQ},
         {TABLE_FINDING_OBSERVATIONS}.{COL_OBSERVATION_ORDINAL}
"""

#: Every observation in a project, each prefixed with its verdict's node id, in
#: arrival order. The per-key summary is folded from these in Python.
SELECT_PROJECT_OBSERVATIONS: Final = _OBSERVATIONS_WITH_NODE + _ARRIVAL_ORDER

SELECT_NODE_OBSERVATIONS: Final = (
    _OBSERVATIONS_WITH_NODE
    + f"  AND {TABLE_VERDICTS}.{COL_VERDICT_NODE_ID} = ?\n"
    + _ARRIVAL_ORDER
)
