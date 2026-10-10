"""Parse Squadron review output into a ``ParsedReview``.

Pure: no I/O, no store, no inbox. Callers in the CLI, the detection tenant, and
the Runner all use the same readers and the same composition.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, NoReturn, cast

import yaml

from amoeba.store.evidence_models import (
    FindingInput,
    RecordSource,
    ReviewVerdict,
    VerdictDerivation,
    parse_severity,
    parse_verdict,
    provider_failure_problem,
)
from amoeba.upstream.squadron import review_fields as fields


class SquadronReviewError(ValueError):
    """Base for every error raised while reading or composing a Squadron review."""


class SquadronParseError(SquadronReviewError):
    """The input could not be read as a review; the message names the problem."""

    def __init__(self, source: RecordSource, message: str) -> None:
        super().__init__(f"{source.value}: {message}")
        self.source = source


class UpstreamVersionError(SquadronReviewError):
    """No usable version label, or the stamp and the caller's label disagree."""


@dataclass(frozen=True, kw_only=True)
class ParsedReview:
    """One review as Squadron reported it, before the caller adds node and path.

    ``upstream_version`` is Squadron's own stamp (``None`` on older output).
    ``slice`` and ``source_document`` are read from files only; they are kept for
    the record id and for callers, and are not part of ``VerdictInput``.
    """

    verdict: ReviewVerdict
    derivation: VerdictDerivation
    fallback_used: bool | None
    findings_parsed: bool | None
    provider_failure: bool
    review_type: str
    model: str
    requested_model: str | None
    diff_truncated: bool | None
    reviewed_sha: str | None
    tool_calls_made: int | None
    score: float | None
    criteria: Mapping[str, object] | None
    sq_run_id: str | None
    findings: tuple[FindingInput, ...]
    source: RecordSource
    upstream_version: str | None
    slice: str | None
    source_document: str | None


# --- Shared value readers (both sources) -----------------------------------


def _fail(source: RecordSource, message: str) -> NoReturn:
    raise SquadronParseError(source, message)


def _typed(raw: Mapping[str, Any], key: str, kind: type, source: RecordSource) -> Any:
    """The value at ``key``, or ``None`` if absent or null. A wrong type raises."""
    value = raw.get(key)
    if value is None:
        return None
    # bool is an int subclass; a flag where a number is expected is a mistake.
    if not isinstance(value, kind) or (isinstance(value, bool) and kind is not bool):
        _fail(source, f"{key!r} has the wrong type: {value!r}")
    return value


def _number(raw: Mapping[str, Any], key: str, source: RecordSource) -> float | None:
    value = raw.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int | float):
        _fail(source, f"{key!r} is not a number: {value!r}")
    return float(value)


def _required(raw: Mapping[str, Any], key: str, source: RecordSource) -> str:
    value = _typed(raw, key, str, source)
    if value is None or not value.strip():
        _fail(source, f"missing required key {key!r}")
    return cast(str, value)


def _read_verdict(
    raw: Mapping[str, Any], key: str, source: RecordSource
) -> ReviewVerdict:
    word = _required(raw, key, source)
    try:
        return parse_verdict(word)
    except ValueError as error:
        raise SquadronParseError(source, str(error)) from error


def _read_derivation(
    raw: Mapping[str, Any], key: str, source: RecordSource
) -> VerdictDerivation:
    word = _typed(raw, key, str, source)
    if word is None:
        return VerdictDerivation.NOT_REPORTED
    try:
        return VerdictDerivation(word.strip().lower())
    except ValueError:
        _fail(source, f"{key!r}: unknown value {word!r}")


def _read_criteria(
    raw: Mapping[str, Any], key: str, source: RecordSource
) -> Mapping[str, object] | None:
    value = _typed(raw, key, dict, source)
    return None if value is None else cast(dict[str, object], value)


def _read_findings(
    items: object, key: str, source: RecordSource
) -> tuple[FindingInput, ...]:
    if items is None:
        return ()
    if not isinstance(items, list):
        _fail(source, f"{key!r} is not a list")
    return tuple(
        _read_finding(item, f"{key}[{index}]", source)
        for index, item in enumerate(cast(list[object], items))
    )


def _read_finding(item: object, label: str, source: RecordSource) -> FindingInput:
    """One finding, identical in both sources. Missing severity or summary raises."""
    if not isinstance(item, dict):
        _fail(source, f"{label} is not a mapping")
    raw = cast(dict[str, Any], item)
    severity_word = raw.get(fields.FINDING_SEVERITY)
    if not isinstance(severity_word, str):
        _fail(source, f"{label} has no {fields.FINDING_SEVERITY!r}")
    try:
        severity = parse_severity(severity_word)
    except ValueError as error:
        raise SquadronParseError(source, f"{label}: {error}") from error
    summary = raw.get(fields.FINDING_SUMMARY)
    if not isinstance(summary, str) or not summary.strip():
        _fail(source, f"{label} has no {fields.FINDING_SUMMARY!r}")
    return FindingInput(
        position_id=_typed(raw, fields.FINDING_ID, str, source),
        severity=severity,
        category=_typed(raw, fields.FINDING_CATEGORY, str, source),
        summary=summary,
        location=_typed(raw, fields.FINDING_LOCATION, str, source),
    )


# --- The review-file reader -------------------------------------------------

_ARTIFACT = RecordSource.ARTIFACT_FRONTMATTER

# A frontmatter fence is a line of `---` plus optional trailing whitespace.
_FENCE = re.compile(r"^---[ \t]*$", re.MULTILINE)


def _heading_pattern(text: str) -> re.Pattern[str]:
    """A markdown heading of any level and case, surrounding whitespace ignored."""
    return re.compile(rf"^#{{1,6}}\s*{re.escape(text)}\s*$", re.MULTILINE | re.I)


_PROVIDER_FAILURE_HEADING = _heading_pattern(fields.HEADING_PROVIDER_FAILURE)
_FINDINGS_NOT_PARSED_HEADING = _heading_pattern(fields.HEADING_FINDINGS_NOT_PARSED)


def _split_frontmatter(text: str) -> tuple[str, str]:
    """The frontmatter text and the body after it. Leading blank lines are allowed."""
    fences = list(_FENCE.finditer(text))
    if len(fences) < 2 or text[: fences[0].start()].strip():
        _fail(_ARTIFACT, "no frontmatter block")
    return text[fences[0].end() : fences[1].start()], text[fences[1].end() :]


def _load_frontmatter(block: str) -> Mapping[str, Any]:
    try:
        loaded: object = yaml.safe_load(block)
    except yaml.YAMLError as error:
        raise SquadronParseError(_ARTIFACT, f"malformed YAML: {error}") from error
    if not isinstance(loaded, dict):
        _fail(_ARTIFACT, "frontmatter is not a mapping")
    return cast(dict[str, Any], loaded)


def parse_review_artifact(text: str) -> ParsedReview:
    """Read a saved Squadron review file (D3, "From a review file")."""
    block, body = _split_frontmatter(text)
    raw = _load_frontmatter(block)
    verdict = _read_verdict(raw, fields.FM_VERDICT, _ARTIFACT)
    findings = _read_findings(
        raw.get(fields.FM_FINDINGS), fields.FM_FINDINGS, _ARTIFACT
    )
    failed = (
        _typed(raw, fields.FM_PROVIDER_FAILURE, bool, _ARTIFACT) is True
        or _PROVIDER_FAILURE_HEADING.search(body) is not None
    )
    problem = provider_failure_problem(
        provider_failure=failed, verdict=verdict, findings=findings
    )
    if problem is not None:
        _fail(_ARTIFACT, problem)
    return ParsedReview(
        verdict=verdict,
        derivation=_read_derivation(raw, fields.FM_VERDICT_SOURCE, _ARTIFACT),
        fallback_used=None,
        findings_parsed=_FINDINGS_NOT_PARSED_HEADING.search(body) is None,
        provider_failure=failed,
        review_type=_required(raw, fields.FM_REVIEW_TYPE, _ARTIFACT),
        model=_required(raw, fields.FM_AI_MODEL, _ARTIFACT),
        requested_model=_typed(raw, fields.FM_REQUESTED_MODEL, str, _ARTIFACT),
        diff_truncated=_typed(raw, fields.FM_DIFF_TRUNCATED, bool, _ARTIFACT),
        reviewed_sha=_typed(raw, fields.FM_REVIEWED_SHA, str, _ARTIFACT),
        tool_calls_made=_typed(raw, fields.FM_TOOL_CALLS_MADE, int, _ARTIFACT),
        score=_number(raw, fields.FM_SCORE, _ARTIFACT),
        criteria=_read_criteria(raw, fields.FM_CRITERIA, _ARTIFACT),
        sq_run_id=_typed(raw, fields.FM_RUN_ID, str, _ARTIFACT),
        findings=findings,
        source=_ARTIFACT,
        upstream_version=_typed(raw, fields.FM_SQUADRON_VERSION, str, _ARTIFACT),
        slice=_typed(raw, fields.FM_SLICE, str, _ARTIFACT),
        source_document=_typed(raw, fields.FM_SOURCE_DOCUMENT, str, _ARTIFACT),
    )
