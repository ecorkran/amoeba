"""Every SQL statement and column name used by the command journal.

Sibling of ``sql.py`` for the same reason ``journal_models.py`` is a sibling of
``models.py``: that module is at its line budget, and the discipline it embodies
is one definition site per name, not one growing file. The rule is unchanged —
a journal column name or statement appears here and nowhere else, so a typo is a
single-definition concern rather than a runtime surprise in a rarely exercised
query.

Statements and names only. Imports neither ``sqlite3`` nor the dataclasses in
``journal_models.py``. Every statement is parameterized; there is no f-string or
concatenated SQL carrying caller data anywhere in this package.
"""

from __future__ import annotations

from typing import Final

# --------------------------------------------------------------------------
# Table name
# --------------------------------------------------------------------------

TABLE_COMMAND_JOURNAL: Final = "command_journal"

# --------------------------------------------------------------------------
# Column names — the single definition site
# --------------------------------------------------------------------------

COL_JOURNAL_ID: Final = "id"
COL_JOURNAL_PROJECT_ID: Final = "project_id"
COL_JOURNAL_NODE_ID: Final = "node_id"
COL_JOURNAL_KIND: Final = "kind"
COL_JOURNAL_PARAMETERS: Final = "parameters"
COL_JOURNAL_ISSUED_AT: Final = "issued_at"
COL_JOURNAL_OUTCOME: Final = "outcome"
COL_JOURNAL_RESULT: Final = "result"
COL_JOURNAL_RESOLVED_AT: Final = "resolved_at"
COL_JOURNAL_RESOLVED_BY: Final = "resolved_by"

#: Index names, so the migration test asserts against a constant rather than a
#: literal repeated between the ``.sql`` file and the test.
INDEX_JOURNAL_UNRESOLVED: Final = "idx_command_journal_unresolved"
INDEX_JOURNAL_PROJECT: Final = "idx_command_journal_project"

#: Column order used by every journal SELECT and by journal row mapping.
#: Declared once so the statements and the mapper cannot disagree about
#: position.
JOURNAL_COLUMNS: Final = (
    COL_JOURNAL_ID,
    COL_JOURNAL_PROJECT_ID,
    COL_JOURNAL_NODE_ID,
    COL_JOURNAL_KIND,
    COL_JOURNAL_PARAMETERS,
    COL_JOURNAL_ISSUED_AT,
    COL_JOURNAL_OUTCOME,
    COL_JOURNAL_RESULT,
    COL_JOURNAL_RESOLVED_AT,
    COL_JOURNAL_RESOLVED_BY,
)

_JOURNAL_SELECT_LIST: Final = ", ".join(
    f"{TABLE_COMMAND_JOURNAL}.{column}" for column in JOURNAL_COLUMNS
)

# --------------------------------------------------------------------------
# Writes
# --------------------------------------------------------------------------

INSERT_JOURNAL_ENTRY: Final = f"""
INSERT INTO {TABLE_COMMAND_JOURNAL} (
    {COL_JOURNAL_ID},
    {COL_JOURNAL_PROJECT_ID},
    {COL_JOURNAL_NODE_ID},
    {COL_JOURNAL_KIND},
    {COL_JOURNAL_PARAMETERS},
    {COL_JOURNAL_ISSUED_AT},
    {COL_JOURNAL_OUTCOME},
    {COL_JOURNAL_RESULT},
    {COL_JOURNAL_RESOLVED_AT},
    {COL_JOURNAL_RESOLVED_BY}
)
VALUES (?, ?, ?, ?, ?, ?, NULL, NULL, NULL, NULL)
"""

#: Closes an entry. The ``outcome IS NULL`` guard makes the already-resolved
#: case a zero-rowcount result rather than a silent overwrite, so the caller
#: raises on it instead of losing the first outcome.
RESOLVE_JOURNAL_ENTRY: Final = f"""
UPDATE {TABLE_COMMAND_JOURNAL}
SET {COL_JOURNAL_OUTCOME} = ?,
    {COL_JOURNAL_RESULT} = ?,
    {COL_JOURNAL_RESOLVED_AT} = ?,
    {COL_JOURNAL_RESOLVED_BY} = ?
WHERE {COL_JOURNAL_ID} = ?
  AND {COL_JOURNAL_OUTCOME} IS NULL
"""

# --------------------------------------------------------------------------
# Reads
# --------------------------------------------------------------------------

SELECT_JOURNAL_ENTRY_BY_ID: Final = f"""
SELECT {_JOURNAL_SELECT_LIST}
FROM {TABLE_COMMAND_JOURNAL}
WHERE {TABLE_COMMAND_JOURNAL}.{COL_JOURNAL_ID} = ?
"""

#: What recovery consumes: unresolved entries for one project, oldest first.
#: Served by the partial index, whose shape matches this WHERE clause.
SELECT_UNRESOLVED_JOURNAL_ENTRIES: Final = f"""
SELECT {_JOURNAL_SELECT_LIST}
FROM {TABLE_COMMAND_JOURNAL}
WHERE {TABLE_COMMAND_JOURNAL}.{COL_JOURNAL_PROJECT_ID} = ?
  AND {TABLE_COMMAND_JOURNAL}.{COL_JOURNAL_OUTCOME} IS NULL
ORDER BY {TABLE_COMMAND_JOURNAL}.{COL_JOURNAL_ISSUED_AT},
         {TABLE_COMMAND_JOURNAL}.{COL_JOURNAL_ID}
"""

#: What inspection consumes. The node and resolved filters are applied by
#: selecting the matching template below, never by concatenating caller data.
SELECT_JOURNAL_ENTRIES_TEMPLATE: Final = f"""
SELECT {_JOURNAL_SELECT_LIST}
FROM {TABLE_COMMAND_JOURNAL}
WHERE {TABLE_COMMAND_JOURNAL}.{COL_JOURNAL_PROJECT_ID} = ?
{{filters}}
ORDER BY {TABLE_COMMAND_JOURNAL}.{COL_JOURNAL_ISSUED_AT},
         {TABLE_COMMAND_JOURNAL}.{COL_JOURNAL_ID}
"""

_FILTER_NODE: Final = f"  AND {TABLE_COMMAND_JOURNAL}.{COL_JOURNAL_NODE_ID} = ?"
_FILTER_UNRESOLVED: Final = (
    f"  AND {TABLE_COMMAND_JOURNAL}.{COL_JOURNAL_OUTCOME} IS NULL"
)


def select_journal_entries(*, by_node: bool, include_resolved: bool) -> str:
    """Render the inspection query for the requested filters.

    Only this module's own constants are ever interpolated; the node id and
    project id always travel as bound parameters. The two flags come from the
    call site's keyword arguments, never from caller-supplied text.
    """
    filters = ""
    if by_node:
        filters += _FILTER_NODE + "\n"
    if not include_resolved:
        filters += _FILTER_UNRESOLVED + "\n"

    return SELECT_JOURNAL_ENTRIES_TEMPLATE.format(filters=filters.rstrip("\n"))


#: Whether a run id has already been recorded in some entry's result. The
#: Squadron matcher's fourth candidate condition: a run already adopted by
#: another entry is not a candidate for this one.
SELECT_ENTRIES_WITH_RESULT: Final = f"""
SELECT {TABLE_COMMAND_JOURNAL}.{COL_JOURNAL_ID},
       {TABLE_COMMAND_JOURNAL}.{COL_JOURNAL_RESULT}
FROM {TABLE_COMMAND_JOURNAL}
WHERE {TABLE_COMMAND_JOURNAL}.{COL_JOURNAL_PROJECT_ID} = ?
  AND {TABLE_COMMAND_JOURNAL}.{COL_JOURNAL_RESULT} IS NOT NULL
"""
