"""Mapping between ``verdicts`` / ``finding_observations`` rows and their records.

Follows ``mapping_inbox.py``: a row that cannot be mapped raises
``UnknownVocabularyValueError`` rather than yielding a defaulted object. Rows are
read by the column names ``sql_evidence`` declares, never by bare position.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import datetime

from amoeba.store import sql_evidence as sq
from amoeba.store.evidence_models import (
    FindingInput,
    FindingObservation,
    FindingSeverity,
    Provenance,
    RecordSource,
    ReviewVerdict,
    VerdictDerivation,
    VerdictInput,
    VerdictRecord,
)
from amoeba.store.finding_identity import (
    RULE_VERSION,
    finding_identity,
    normalize_location,
    normalize_summary,
)
from amoeba.store.mapping_journal import decode_mapping, decode_timestamp
from amoeba.store.models import UnknownVocabularyValueError


def _columns(
    row: Sequence[object], columns: tuple[str, ...], table: str
) -> dict[str, object]:
    if len(row) != len(columns):
        raise UnknownVocabularyValueError(
            f"{table} row has {len(row)} columns, expected {len(columns)}"
        )
    return dict(zip(columns, row, strict=True))


def _vocabulary[
    VocabularyT: (ReviewVerdict, FindingSeverity, VerdictDerivation, RecordSource)
](value: object, vocabulary: type[VocabularyT], column: str) -> VocabularyT:
    """Coerce a stored value into a closed evidence vocabulary, or raise."""
    if not isinstance(value, str):
        raise UnknownVocabularyValueError(f"{column} is not a string: {value!r}")
    try:
        return vocabulary(value)
    except ValueError as error:
        # Specific: the stored string is outside the vocabulary. Re-raised so
        # the caller never receives a defaulted record.
        raise UnknownVocabularyValueError(
            f"{column} value {value!r} is not a valid {vocabulary.__name__}"
        ) from error


def _text(value: object, column: str) -> str:
    if not isinstance(value, str):
        raise UnknownVocabularyValueError(f"{column} is not a string: {value!r}")
    return value


def _optional_text(value: object, column: str) -> str | None:
    return None if value is None else _text(value, column)


def _integer(value: object, column: str) -> int:
    if not isinstance(value, int):
        raise UnknownVocabularyValueError(f"{column} is not an integer: {value!r}")
    return value


def _optional_integer(value: object, column: str) -> int | None:
    return None if value is None else _integer(value, column)


def _optional_bool(value: object, column: str) -> bool | None:
    if value is None:
        return None
    if value not in (0, 1) or isinstance(value, float):
        raise UnknownVocabularyValueError(f"{column} is not 0 or 1: {value!r}")
    return value == 1


def _optional_float(value: object, column: str) -> float | None:
    if value is None:
        return None
    if not isinstance(value, int | float):
        raise UnknownVocabularyValueError(f"{column} is not a number: {value!r}")
    return float(value)


def _required_timestamp(value: object, column: str) -> datetime:
    decoded = decode_timestamp(value, column)
    if decoded is None:
        raise UnknownVocabularyValueError(f"{column} is NULL")
    return decoded


def _optional_flag(value: bool | None) -> int | None:
    return None if value is None else int(value)


def map_verdict(
    row: Sequence[object], findings: tuple[FindingInput, ...]
) -> VerdictRecord:
    """Map one ``verdicts`` row, plus its findings, to a :class:`VerdictRecord`.

    Raises:
        UnknownVocabularyValueError: If the row is the wrong width or carries a
            value that cannot be mapped.
    """
    c = _columns(row, sq.VERDICT_COLUMNS, sq.TABLE_VERDICTS)
    provider_failure = _optional_bool(
        c[sq.COL_VERDICT_PROVIDER_FAILURE], sq.COL_VERDICT_PROVIDER_FAILURE
    )
    if provider_failure is None:
        raise UnknownVocabularyValueError(f"{sq.COL_VERDICT_PROVIDER_FAILURE} is NULL")
    criteria = c[sq.COL_VERDICT_CRITERIA]
    return VerdictRecord(
        recorded_seq=_integer(
            c[sq.COL_VERDICT_RECORDED_SEQ], sq.COL_VERDICT_RECORDED_SEQ
        ),
        id=_text(c[sq.COL_VERDICT_ID], sq.COL_VERDICT_ID),
        project_id=_text(c[sq.COL_VERDICT_PROJECT_ID], sq.COL_VERDICT_PROJECT_ID),
        node_id=_text(c[sq.COL_VERDICT_NODE_ID], sq.COL_VERDICT_NODE_ID),
        journal_entry_id=_optional_text(
            c[sq.COL_VERDICT_JOURNAL_ENTRY_ID], sq.COL_VERDICT_JOURNAL_ENTRY_ID
        ),
        verdict=_vocabulary(
            c[sq.COL_VERDICT_VERDICT], ReviewVerdict, sq.COL_VERDICT_VERDICT
        ),
        derivation=_vocabulary(
            c[sq.COL_VERDICT_DERIVATION], VerdictDerivation, sq.COL_VERDICT_DERIVATION
        ),
        fallback_used=_optional_bool(
            c[sq.COL_VERDICT_FALLBACK_USED], sq.COL_VERDICT_FALLBACK_USED
        ),
        findings_parsed=_optional_bool(
            c[sq.COL_VERDICT_FINDINGS_PARSED], sq.COL_VERDICT_FINDINGS_PARSED
        ),
        diff_truncated=_optional_bool(
            c[sq.COL_VERDICT_DIFF_TRUNCATED], sq.COL_VERDICT_DIFF_TRUNCATED
        ),
        provider_failure=provider_failure,
        review_type=_text(c[sq.COL_VERDICT_REVIEW_TYPE], sq.COL_VERDICT_REVIEW_TYPE),
        model=_text(c[sq.COL_VERDICT_MODEL], sq.COL_VERDICT_MODEL),
        requested_model=_optional_text(
            c[sq.COL_VERDICT_REQUESTED_MODEL], sq.COL_VERDICT_REQUESTED_MODEL
        ),
        reviewed_sha=_optional_text(
            c[sq.COL_VERDICT_REVIEWED_SHA], sq.COL_VERDICT_REVIEWED_SHA
        ),
        score=_optional_float(c[sq.COL_VERDICT_SCORE], sq.COL_VERDICT_SCORE),
        criteria=(
            None
            if criteria is None
            else decode_mapping(criteria, sq.COL_VERDICT_CRITERIA)
        ),
        tool_calls_made=_optional_integer(
            c[sq.COL_VERDICT_TOOL_CALLS_MADE], sq.COL_VERDICT_TOOL_CALLS_MADE
        ),
        sq_run_id=_optional_text(c[sq.COL_VERDICT_SQ_RUN_ID], sq.COL_VERDICT_SQ_RUN_ID),
        findings=findings,
        provenance=Provenance(
            upstream=_text(c[sq.COL_VERDICT_UPSTREAM], sq.COL_VERDICT_UPSTREAM),
            upstream_version=_text(
                c[sq.COL_VERDICT_UPSTREAM_VERSION], sq.COL_VERDICT_UPSTREAM_VERSION
            ),
            source=_vocabulary(
                c[sq.COL_VERDICT_SOURCE], RecordSource, sq.COL_VERDICT_SOURCE
            ),
            source_path=_optional_text(
                c[sq.COL_VERDICT_SOURCE_PATH], sq.COL_VERDICT_SOURCE_PATH
            ),
        ),
        recorded_at=_required_timestamp(
            c[sq.COL_VERDICT_RECORDED_AT], sq.COL_VERDICT_RECORDED_AT
        ),
    )


def map_observation(row: Sequence[object]) -> FindingObservation:
    """Map one ``finding_observations`` row to a :class:`FindingObservation`.

    Raises:
        UnknownVocabularyValueError: If the row is the wrong width or carries a
            value that cannot be mapped.
    """
    c = _columns(row, sq.OBSERVATION_COLUMNS, sq.TABLE_FINDING_OBSERVATIONS)
    return FindingObservation(
        verdict_id=_text(
            c[sq.COL_OBSERVATION_VERDICT_ID], sq.COL_OBSERVATION_VERDICT_ID
        ),
        ordinal=_integer(c[sq.COL_OBSERVATION_ORDINAL], sq.COL_OBSERVATION_ORDINAL),
        position_id=_optional_text(
            c[sq.COL_OBSERVATION_POSITION_ID], sq.COL_OBSERVATION_POSITION_ID
        ),
        severity=_vocabulary(
            c[sq.COL_OBSERVATION_SEVERITY], FindingSeverity, sq.COL_OBSERVATION_SEVERITY
        ),
        category=_optional_text(
            c[sq.COL_OBSERVATION_CATEGORY], sq.COL_OBSERVATION_CATEGORY
        ),
        summary=_text(c[sq.COL_OBSERVATION_SUMMARY], sq.COL_OBSERVATION_SUMMARY),
        location=_optional_text(
            c[sq.COL_OBSERVATION_LOCATION], sq.COL_OBSERVATION_LOCATION
        ),
        normalized_location=_text(
            c[sq.COL_OBSERVATION_NORMALIZED_LOCATION],
            sq.COL_OBSERVATION_NORMALIZED_LOCATION,
        ),
        normalized_summary=_text(
            c[sq.COL_OBSERVATION_NORMALIZED_SUMMARY],
            sq.COL_OBSERVATION_NORMALIZED_SUMMARY,
        ),
        identity=_text(c[sq.COL_OBSERVATION_IDENTITY], sq.COL_OBSERVATION_IDENTITY),
        identity_version=_integer(
            c[sq.COL_OBSERVATION_IDENTITY_VERSION], sq.COL_OBSERVATION_IDENTITY_VERSION
        ),
    )


def observation_as_finding(observation: FindingObservation) -> FindingInput:
    """The finding as the reviewer gave it, recovered from its stored row."""
    return FindingInput(
        severity=observation.severity,
        summary=observation.summary,
        position_id=observation.position_id,
        category=observation.category,
        location=observation.location,
    )


def verdict_parameters(
    verdict: VerdictInput, project_id: str, recorded_at: str
) -> tuple[object, ...]:
    """Insert parameters for one verdict, in ``VERDICT_INSERT_COLUMNS`` order."""
    by_column: dict[str, object] = {
        sq.COL_VERDICT_ID: verdict.id,
        sq.COL_VERDICT_PROJECT_ID: project_id,
        sq.COL_VERDICT_NODE_ID: verdict.node_id,
        sq.COL_VERDICT_JOURNAL_ENTRY_ID: verdict.journal_entry_id,
        sq.COL_VERDICT_VERDICT: verdict.verdict.value,
        sq.COL_VERDICT_DERIVATION: verdict.derivation.value,
        sq.COL_VERDICT_FALLBACK_USED: _optional_flag(verdict.fallback_used),
        sq.COL_VERDICT_FINDINGS_PARSED: _optional_flag(verdict.findings_parsed),
        sq.COL_VERDICT_DIFF_TRUNCATED: _optional_flag(verdict.diff_truncated),
        sq.COL_VERDICT_PROVIDER_FAILURE: int(verdict.provider_failure),
        sq.COL_VERDICT_REVIEW_TYPE: verdict.review_type,
        sq.COL_VERDICT_MODEL: verdict.model,
        sq.COL_VERDICT_REQUESTED_MODEL: verdict.requested_model,
        sq.COL_VERDICT_REVIEWED_SHA: verdict.reviewed_sha,
        sq.COL_VERDICT_SCORE: verdict.score,
        sq.COL_VERDICT_CRITERIA: (
            None if verdict.criteria is None else json.dumps(dict(verdict.criteria))
        ),
        sq.COL_VERDICT_TOOL_CALLS_MADE: verdict.tool_calls_made,
        sq.COL_VERDICT_SQ_RUN_ID: verdict.sq_run_id,
        sq.COL_VERDICT_UPSTREAM: verdict.provenance.upstream,
        sq.COL_VERDICT_UPSTREAM_VERSION: verdict.provenance.upstream_version,
        sq.COL_VERDICT_SOURCE: verdict.provenance.source.value,
        sq.COL_VERDICT_SOURCE_PATH: verdict.provenance.source_path,
        sq.COL_VERDICT_RECORDED_AT: recorded_at,
    }
    return tuple(by_column[column] for column in sq.VERDICT_INSERT_COLUMNS)


def observation_parameters(
    verdict_id: str, ordinal: int, finding: FindingInput
) -> tuple[object, ...]:
    """Insert parameters for one finding, keyed under the current rule version."""
    by_column: dict[str, object] = {
        sq.COL_OBSERVATION_VERDICT_ID: verdict_id,
        sq.COL_OBSERVATION_ORDINAL: ordinal,
        sq.COL_OBSERVATION_POSITION_ID: finding.position_id,
        sq.COL_OBSERVATION_SEVERITY: finding.severity.value,
        sq.COL_OBSERVATION_CATEGORY: finding.category,
        sq.COL_OBSERVATION_SUMMARY: finding.summary,
        sq.COL_OBSERVATION_LOCATION: finding.location,
        sq.COL_OBSERVATION_NORMALIZED_LOCATION: normalize_location(finding.location),
        sq.COL_OBSERVATION_NORMALIZED_SUMMARY: normalize_summary(finding.summary),
        sq.COL_OBSERVATION_IDENTITY: finding_identity(
            finding.location, finding.summary
        ),
        sq.COL_OBSERVATION_IDENTITY_VERSION: RULE_VERSION,
    }
    return tuple(by_column[column] for column in sq.OBSERVATION_COLUMNS)
