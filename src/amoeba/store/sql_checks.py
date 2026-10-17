"""Every SQL statement and column name for checks and progress records, and the
row mapping for checks.

Sibling of ``sql_evidence.py`` under the same rule: a column name or statement
for ``check_results`` or ``progress_records`` appears here and in migration
``007`` and nowhere else. Every value is a bound parameter. The row mapping
lives here too, since two small tables do not earn two files; it raises
``UnknownVocabularyValueError`` rather than yielding a defaulted record.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import datetime
from typing import Final

from amoeba.store.check_models import (
    CheckInput,
    CheckOutcome,
    CheckRecord,
    ProgressInput,
)
from amoeba.store.evidence_models import Provenance, RecordSource
from amoeba.store.mapping_journal import decode_mapping, decode_timestamp
from amoeba.store.models import UnknownVocabularyValueError
from amoeba.store.row_values import integer as _integer
from amoeba.store.row_values import optional_text as _optional_text
from amoeba.store.row_values import text as _text

TABLE_CHECK_RESULTS: Final = "check_results"
TABLE_PROGRESS_RECORDS: Final = "progress_records"

# --------------------------------------------------------------------------
# check_results columns — the single definition site
# --------------------------------------------------------------------------

COL_CHECK_RECORDED_SEQ: Final = "recorded_seq"
COL_CHECK_ID: Final = "id"
COL_CHECK_PROJECT_ID: Final = "project_id"
COL_CHECK_NODE_ID: Final = "node_id"
COL_CHECK_NAME: Final = "name"
COL_CHECK_OUTCOME: Final = "outcome"
COL_CHECK_EXAMINED_COUNT: Final = "examined_count"
COL_CHECK_EXAMINED: Final = "examined"
COL_CHECK_BASELINE_REF: Final = "baseline_ref"
COL_CHECK_UPSTREAM: Final = "upstream"
COL_CHECK_UPSTREAM_VERSION: Final = "upstream_version"
COL_CHECK_SOURCE: Final = "source"
COL_CHECK_SOURCE_PATH: Final = "source_path"
COL_CHECK_RECORDED_AT: Final = "recorded_at"

#: Column order for every check SELECT and for row mapping.
CHECK_COLUMNS: Final = (
    COL_CHECK_RECORDED_SEQ,
    COL_CHECK_ID,
    COL_CHECK_PROJECT_ID,
    COL_CHECK_NODE_ID,
    COL_CHECK_NAME,
    COL_CHECK_OUTCOME,
    COL_CHECK_EXAMINED_COUNT,
    COL_CHECK_EXAMINED,
    COL_CHECK_BASELINE_REF,
    COL_CHECK_UPSTREAM,
    COL_CHECK_UPSTREAM_VERSION,
    COL_CHECK_SOURCE,
    COL_CHECK_SOURCE_PATH,
    COL_CHECK_RECORDED_AT,
)

#: ``recorded_seq`` is omitted from inserts so SQLite assigns arrival order.
CHECK_INSERT_COLUMNS: Final = CHECK_COLUMNS[1:]

# --------------------------------------------------------------------------
# progress_records columns — the single definition site
# --------------------------------------------------------------------------

COL_PROGRESS_RECORDED_SEQ: Final = "recorded_seq"
COL_PROGRESS_ID: Final = "id"
COL_PROGRESS_PROJECT_ID: Final = "project_id"
COL_PROGRESS_NODE_ID: Final = "node_id"
COL_PROGRESS_KIND: Final = "progress_kind"
COL_PROGRESS_CONTENT: Final = "content"
COL_PROGRESS_UPSTREAM: Final = "upstream"
COL_PROGRESS_UPSTREAM_VERSION: Final = "upstream_version"
COL_PROGRESS_SOURCE: Final = "source"
COL_PROGRESS_SOURCE_PATH: Final = "source_path"
COL_PROGRESS_RECORDED_AT: Final = "recorded_at"

#: Insert order; ``recorded_seq`` is assigned by SQLite.
PROGRESS_INSERT_COLUMNS: Final = (
    COL_PROGRESS_ID,
    COL_PROGRESS_PROJECT_ID,
    COL_PROGRESS_NODE_ID,
    COL_PROGRESS_KIND,
    COL_PROGRESS_CONTENT,
    COL_PROGRESS_UPSTREAM,
    COL_PROGRESS_UPSTREAM_VERSION,
    COL_PROGRESS_SOURCE,
    COL_PROGRESS_SOURCE_PATH,
    COL_PROGRESS_RECORDED_AT,
)

#: Index names, so the migration test asserts against constants.
INDEX_CHECK_RESULTS_NODE: Final = "idx_check_results_node"
INDEX_PROGRESS_RECORDS_NODE: Final = "idx_progress_records_node"
INDEX_VERDICTS_JUDGE_INVOCATION: Final = "idx_verdicts_judge_invocation"


def _placeholders(count: int) -> str:
    return ", ".join("?" for _ in range(count))


_CHECK_SELECT_LIST: Final = ", ".join(CHECK_COLUMNS)

INSERT_CHECK: Final = f"""
INSERT INTO {TABLE_CHECK_RESULTS} ({", ".join(CHECK_INSERT_COLUMNS)})
VALUES ({_placeholders(len(CHECK_INSERT_COLUMNS))})
"""

SELECT_CHECK_BY_ID: Final = f"""
SELECT {_CHECK_SELECT_LIST}
FROM {TABLE_CHECK_RESULTS}
WHERE {COL_CHECK_ID} = ?
"""

SELECT_CHECKS: Final = f"""
SELECT {_CHECK_SELECT_LIST}
FROM {TABLE_CHECK_RESULTS}
WHERE {COL_CHECK_PROJECT_ID} = ?
ORDER BY {COL_CHECK_RECORDED_SEQ}
"""

SELECT_CHECKS_FOR_NODE: Final = f"""
SELECT {_CHECK_SELECT_LIST}
FROM {TABLE_CHECK_RESULTS}
WHERE {COL_CHECK_PROJECT_ID} = ?
  AND {COL_CHECK_NODE_ID} = ?
ORDER BY {COL_CHECK_RECORDED_SEQ}
"""

INSERT_PROGRESS: Final = f"""
INSERT INTO {TABLE_PROGRESS_RECORDS} ({", ".join(PROGRESS_INSERT_COLUMNS)})
VALUES ({_placeholders(len(PROGRESS_INSERT_COLUMNS))})
"""

# --------------------------------------------------------------------------
# Row mapping and insert parameters
# --------------------------------------------------------------------------


def _vocabulary[VocabularyT: (CheckOutcome, RecordSource)](
    value: object, vocabulary: type[VocabularyT], column: str
) -> VocabularyT:
    word = _text(value, column)
    try:
        return vocabulary(word)
    except ValueError as error:
        # Specific: the stored string is outside the vocabulary. Re-raised so
        # the caller never receives a defaulted record.
        raise UnknownVocabularyValueError(
            f"{column} value {word!r} is not a valid {vocabulary.__name__}"
        ) from error


def _recorded_at(value: object) -> datetime:
    decoded = decode_timestamp(value, COL_CHECK_RECORDED_AT)
    if decoded is None:
        raise UnknownVocabularyValueError(f"{COL_CHECK_RECORDED_AT} is NULL")
    return decoded


def map_check(row: Sequence[object]) -> CheckRecord:
    """Map one ``check_results`` row to a :class:`CheckRecord`.

    Raises:
        UnknownVocabularyValueError: If the row is the wrong width or carries a
            value that cannot be mapped.
    """
    if len(row) != len(CHECK_COLUMNS):
        raise UnknownVocabularyValueError(
            f"{TABLE_CHECK_RESULTS} row has {len(row)} columns, "
            f"expected {len(CHECK_COLUMNS)}"
        )
    c = dict(zip(CHECK_COLUMNS, row, strict=True))
    examined = c[COL_CHECK_EXAMINED]
    count = c[COL_CHECK_EXAMINED_COUNT]
    return CheckRecord(
        recorded_seq=_integer(c[COL_CHECK_RECORDED_SEQ], COL_CHECK_RECORDED_SEQ),
        id=_text(c[COL_CHECK_ID], COL_CHECK_ID),
        project_id=_text(c[COL_CHECK_PROJECT_ID], COL_CHECK_PROJECT_ID),
        node_id=_text(c[COL_CHECK_NODE_ID], COL_CHECK_NODE_ID),
        name=_text(c[COL_CHECK_NAME], COL_CHECK_NAME),
        outcome=_vocabulary(c[COL_CHECK_OUTCOME], CheckOutcome, COL_CHECK_OUTCOME),
        examined_count=(
            None if count is None else _integer(count, COL_CHECK_EXAMINED_COUNT)
        ),
        examined=(
            None if examined is None else decode_mapping(examined, COL_CHECK_EXAMINED)
        ),
        baseline_ref=_optional_text(c[COL_CHECK_BASELINE_REF], COL_CHECK_BASELINE_REF),
        provenance=Provenance(
            upstream=_text(c[COL_CHECK_UPSTREAM], COL_CHECK_UPSTREAM),
            upstream_version=_text(
                c[COL_CHECK_UPSTREAM_VERSION], COL_CHECK_UPSTREAM_VERSION
            ),
            source=_vocabulary(c[COL_CHECK_SOURCE], RecordSource, COL_CHECK_SOURCE),
            source_path=_optional_text(c[COL_CHECK_SOURCE_PATH], COL_CHECK_SOURCE_PATH),
        ),
        recorded_at=_recorded_at(c[COL_CHECK_RECORDED_AT]),
    )


def check_parameters(
    check: CheckInput, project_id: str, recorded_at: str
) -> tuple[object, ...]:
    """Insert parameters for one check, in ``CHECK_INSERT_COLUMNS`` order."""
    by_column: dict[str, object] = {
        COL_CHECK_ID: check.id,
        COL_CHECK_PROJECT_ID: project_id,
        COL_CHECK_NODE_ID: check.node_id,
        COL_CHECK_NAME: check.name,
        COL_CHECK_OUTCOME: check.outcome.value,
        COL_CHECK_EXAMINED_COUNT: check.examined_count,
        COL_CHECK_EXAMINED: (
            None if check.examined is None else json.dumps(dict(check.examined))
        ),
        COL_CHECK_BASELINE_REF: check.baseline_ref,
        COL_CHECK_UPSTREAM: check.provenance.upstream,
        COL_CHECK_UPSTREAM_VERSION: check.provenance.upstream_version,
        COL_CHECK_SOURCE: check.provenance.source.value,
        COL_CHECK_SOURCE_PATH: check.provenance.source_path,
        COL_CHECK_RECORDED_AT: recorded_at,
    }
    return tuple(by_column[column] for column in CHECK_INSERT_COLUMNS)


def progress_parameters(
    progress: ProgressInput, project_id: str, recorded_at: str
) -> tuple[object, ...]:
    """Insert parameters for one progress record, in insert-column order."""
    by_column: dict[str, object] = {
        COL_PROGRESS_ID: progress.id,
        COL_PROGRESS_PROJECT_ID: project_id,
        COL_PROGRESS_NODE_ID: progress.node_id,
        COL_PROGRESS_KIND: progress.progress_kind.value,
        COL_PROGRESS_CONTENT: json.dumps(dict(progress.content)),
        COL_PROGRESS_UPSTREAM: progress.provenance.upstream,
        COL_PROGRESS_UPSTREAM_VERSION: progress.provenance.upstream_version,
        COL_PROGRESS_SOURCE: progress.provenance.source.value,
        COL_PROGRESS_SOURCE_PATH: progress.provenance.source_path,
        COL_PROGRESS_RECORDED_AT: recorded_at,
    }
    return tuple(by_column[column] for column in PROGRESS_INSERT_COLUMNS)
