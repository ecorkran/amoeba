"""Read a saved Squadron review file (frontmatter plus body headings)."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any, cast

import yaml

from amoeba.store.evidence_models import RecordSource, provider_failure_problem
from amoeba.upstream.squadron import review_fields as fields
from amoeba.upstream.squadron.review import ParsedReview, SquadronParseError
from amoeba.upstream.squadron.review_values import (
    fail,
    number,
    read_criteria,
    read_derivation,
    read_findings,
    read_verdict,
    required,
    typed,
)

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
        fail(_ARTIFACT, "no frontmatter block")
    return text[fences[0].end() : fences[1].start()], text[fences[1].end() :]


def _load_frontmatter(block: str) -> Mapping[str, Any]:
    try:
        loaded: object = yaml.safe_load(block)
    except yaml.YAMLError as error:
        raise SquadronParseError(_ARTIFACT, f"malformed YAML: {error}") from error
    if not isinstance(loaded, dict):
        fail(_ARTIFACT, "frontmatter is not a mapping")
    return cast(dict[str, Any], loaded)


def parse_review_artifact(text: str) -> ParsedReview:
    """Read a saved Squadron review file (D3, "From a review file")."""
    block, body = _split_frontmatter(text)
    raw = _load_frontmatter(block)
    verdict = read_verdict(raw, fields.FM_VERDICT, _ARTIFACT)
    findings = read_findings(raw.get(fields.FM_FINDINGS), fields.FM_FINDINGS, _ARTIFACT)
    failed = (
        typed(raw, fields.FM_PROVIDER_FAILURE, bool, _ARTIFACT) is True
        or _PROVIDER_FAILURE_HEADING.search(body) is not None
    )
    problem = provider_failure_problem(
        provider_failure=failed, verdict=verdict, findings=findings
    )
    if problem is not None:
        fail(_ARTIFACT, problem)
    return ParsedReview(
        verdict=verdict,
        derivation=read_derivation(raw, fields.FM_VERDICT_SOURCE, _ARTIFACT),
        fallback_used=None,
        findings_parsed=_FINDINGS_NOT_PARSED_HEADING.search(body) is None,
        provider_failure=failed,
        review_type=required(raw, fields.FM_REVIEW_TYPE, _ARTIFACT),
        model=required(raw, fields.FM_AI_MODEL, _ARTIFACT),
        requested_model=typed(raw, fields.FM_REQUESTED_MODEL, str, _ARTIFACT),
        diff_truncated=typed(raw, fields.FM_DIFF_TRUNCATED, bool, _ARTIFACT),
        reviewed_sha=typed(raw, fields.FM_REVIEWED_SHA, str, _ARTIFACT),
        tool_calls_made=typed(raw, fields.FM_TOOL_CALLS_MADE, int, _ARTIFACT),
        score=number(raw, fields.FM_SCORE, _ARTIFACT),
        criteria=read_criteria(raw, fields.FM_CRITERIA, _ARTIFACT),
        sq_run_id=typed(raw, fields.FM_RUN_ID, str, _ARTIFACT),
        findings=findings,
        source=_ARTIFACT,
        upstream_version=typed(raw, fields.FM_SQUADRON_VERSION, str, _ARTIFACT),
        slice=typed(raw, fields.FM_SLICE, str, _ARTIFACT),
        source_document=typed(raw, fields.FM_SOURCE_DOCUMENT, str, _ARTIFACT),
    )
