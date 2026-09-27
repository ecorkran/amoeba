"""The ``verdict`` submission's payload keys, and building a ``VerdictInput`` from it.

The payload is ``VerdictInput``'s fields except ``id``, with ``provenance``
flattened to ``upstream``, ``upstream_version``, ``source``, and
``source_path``. Each key is defined once, here; ``amoeba.inbox``'s
``VerdictPayload`` uses them as its field names and a test pins the two.

The store receives the payload as a plain, already-validated mapping and never
imports pydantic. A malformed value raises ``ValueError``: envelope validation
upstream should have made that impossible.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final, cast

from amoeba.store.evidence_models import (
    FindingInput,
    FindingSeverity,
    Provenance,
    RecordSource,
    ReviewVerdict,
    VerdictDerivation,
    VerdictInput,
)

VERDICT_NODE_ID: Final = "node_id"
VERDICT_VERDICT: Final = "verdict"
VERDICT_DERIVATION: Final = "derivation"
VERDICT_FALLBACK_USED: Final = "fallback_used"
VERDICT_FINDINGS_PARSED: Final = "findings_parsed"
VERDICT_PROVIDER_FAILURE: Final = "provider_failure"
VERDICT_DIFF_TRUNCATED: Final = "diff_truncated"
VERDICT_REVIEW_TYPE: Final = "review_type"
VERDICT_MODEL: Final = "model"
VERDICT_REQUESTED_MODEL: Final = "requested_model"
VERDICT_REVIEWED_SHA: Final = "reviewed_sha"
VERDICT_SCORE: Final = "score"
VERDICT_CRITERIA: Final = "criteria"
VERDICT_TOOL_CALLS_MADE: Final = "tool_calls_made"
VERDICT_SQ_RUN_ID: Final = "sq_run_id"
VERDICT_JOURNAL_ENTRY_ID: Final = "journal_entry_id"
VERDICT_FINDINGS: Final = "findings"
VERDICT_UPSTREAM: Final = "upstream"
VERDICT_UPSTREAM_VERSION: Final = "upstream_version"
VERDICT_SOURCE: Final = "source"
VERDICT_SOURCE_PATH: Final = "source_path"

FINDING_POSITION_ID: Final = "position_id"
FINDING_SEVERITY: Final = "severity"
FINDING_CATEGORY: Final = "category"
FINDING_SUMMARY: Final = "summary"
FINDING_LOCATION: Final = "location"

#: Every key of the ``verdict`` payload, for the test pinning ``VerdictPayload``.
VERDICT_PAYLOAD_KEYS: Final = frozenset(
    {
        VERDICT_NODE_ID,
        VERDICT_VERDICT,
        VERDICT_DERIVATION,
        VERDICT_FALLBACK_USED,
        VERDICT_FINDINGS_PARSED,
        VERDICT_PROVIDER_FAILURE,
        VERDICT_DIFF_TRUNCATED,
        VERDICT_REVIEW_TYPE,
        VERDICT_MODEL,
        VERDICT_REQUESTED_MODEL,
        VERDICT_REVIEWED_SHA,
        VERDICT_SCORE,
        VERDICT_CRITERIA,
        VERDICT_TOOL_CALLS_MADE,
        VERDICT_SQ_RUN_ID,
        VERDICT_JOURNAL_ENTRY_ID,
        VERDICT_FINDINGS,
        VERDICT_UPSTREAM,
        VERDICT_UPSTREAM_VERSION,
        VERDICT_SOURCE,
        VERDICT_SOURCE_PATH,
    }
)

FINDING_PAYLOAD_KEYS: Final = frozenset(
    {
        FINDING_POSITION_ID,
        FINDING_SEVERITY,
        FINDING_CATEGORY,
        FINDING_SUMMARY,
        FINDING_LOCATION,
    }
)


def _malformed(key: str, value: object, expected: str) -> ValueError:
    return ValueError(f"verdict payload {key!r} must be {expected}: {value!r}")


def _text(payload: Mapping[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str):
        raise _malformed(key, value, "a string")
    return value


def _optional_text(payload: Mapping[str, object], key: str) -> str | None:
    return None if payload.get(key) is None else _text(payload, key)


def _optional_bool(payload: Mapping[str, object], key: str) -> bool | None:
    value = payload.get(key)
    if value is not None and not isinstance(value, bool):
        raise _malformed(key, value, "true, false, or null")
    return value


def _bool(payload: Mapping[str, object], key: str) -> bool:
    value = _optional_bool(payload, key)
    if value is None:
        raise _malformed(key, value, "true or false")
    return value


def _optional_int(payload: Mapping[str, object], key: str) -> int | None:
    value = payload.get(key)
    if value is not None and (not isinstance(value, int) or isinstance(value, bool)):
        raise _malformed(key, value, "an integer or null")
    return value


def _optional_float(payload: Mapping[str, object], key: str) -> float | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise _malformed(key, value, "a number or null")
    return float(value)


def _optional_mapping(
    payload: Mapping[str, object], key: str
) -> Mapping[str, object] | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise _malformed(key, value, "an object or null")
    return cast(Mapping[str, object], value)


def _member[
    VocabularyT: (ReviewVerdict, FindingSeverity, VerdictDerivation, RecordSource)
](
    payload: Mapping[str, object], key: str, vocabulary: type[VocabularyT]
) -> VocabularyT:
    value = payload.get(key)
    if not isinstance(value, str):
        raise _malformed(key, value, f"a {vocabulary.__name__}")
    try:
        return vocabulary(value)
    except ValueError:
        raise _malformed(key, value, f"a {vocabulary.__name__}") from None


def _finding(entry: object) -> FindingInput:
    if not isinstance(entry, Mapping):
        raise _malformed(VERDICT_FINDINGS, entry, "a list of objects")
    item = cast(Mapping[str, object], entry)
    return FindingInput(
        severity=_member(item, FINDING_SEVERITY, FindingSeverity),
        summary=_text(item, FINDING_SUMMARY),
        position_id=_optional_text(item, FINDING_POSITION_ID),
        category=_optional_text(item, FINDING_CATEGORY),
        location=_optional_text(item, FINDING_LOCATION),
    )


def _findings(payload: Mapping[str, object]) -> tuple[FindingInput, ...]:
    value = payload.get(VERDICT_FINDINGS)
    if not isinstance(value, list | tuple):
        raise _malformed(VERDICT_FINDINGS, value, "a list")
    return tuple(_finding(entry) for entry in cast(list[object], value))


def verdict_from_payload(
    submission_id: str, payload: Mapping[str, object]
) -> VerdictInput:
    """Build the ``VerdictInput`` a submission describes; its id is the record id."""
    return VerdictInput(
        id=submission_id,
        node_id=_text(payload, VERDICT_NODE_ID),
        verdict=_member(payload, VERDICT_VERDICT, ReviewVerdict),
        derivation=_member(payload, VERDICT_DERIVATION, VerdictDerivation),
        fallback_used=_optional_bool(payload, VERDICT_FALLBACK_USED),
        findings_parsed=_optional_bool(payload, VERDICT_FINDINGS_PARSED),
        provider_failure=_bool(payload, VERDICT_PROVIDER_FAILURE),
        diff_truncated=_optional_bool(payload, VERDICT_DIFF_TRUNCATED),
        review_type=_text(payload, VERDICT_REVIEW_TYPE),
        model=_text(payload, VERDICT_MODEL),
        requested_model=_optional_text(payload, VERDICT_REQUESTED_MODEL),
        reviewed_sha=_optional_text(payload, VERDICT_REVIEWED_SHA),
        score=_optional_float(payload, VERDICT_SCORE),
        criteria=_optional_mapping(payload, VERDICT_CRITERIA),
        tool_calls_made=_optional_int(payload, VERDICT_TOOL_CALLS_MADE),
        sq_run_id=_optional_text(payload, VERDICT_SQ_RUN_ID),
        journal_entry_id=_optional_text(payload, VERDICT_JOURNAL_ENTRY_ID),
        findings=_findings(payload),
        provenance=Provenance(
            upstream=_text(payload, VERDICT_UPSTREAM),
            upstream_version=_text(payload, VERDICT_UPSTREAM_VERSION),
            source=_member(payload, VERDICT_SOURCE, RecordSource),
            source_path=_optional_text(payload, VERDICT_SOURCE_PATH),
        ),
    )
