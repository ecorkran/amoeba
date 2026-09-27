"""Builders for verdict inputs, shared by the store, inbox, and CLI evidence tests."""

from __future__ import annotations

import dataclasses
from pathlib import Path

from review_fixtures import (
    CapturedFinding,
    has_provider_failure_heading,
    read_frontmatter,
    review_findings,
)

from amoeba.store import (
    FindingInput,
    FindingSeverity,
    NodeKind,
    Provenance,
    RecordSource,
    ReviewVerdict,
    Store,
    VerdictDerivation,
    VerdictInput,
    parse_severity,
    parse_verdict,
)

PROJECT = "demo"
REVIEW_TYPE = "tasks"
UPSTREAM_VERSION = "0.14.0"

PROVENANCE = Provenance(
    upstream="squadron",
    upstream_version=UPSTREAM_VERSION,
    source=RecordSource.ARTIFACT_FRONTMATTER,
)


def seed_node(store: Store, project_id: str = PROJECT) -> str:
    return store.create_node(
        project_id=project_id, kind=NodeKind.SLICE, title="reviewed"
    ).id


def finding(
    summary: str,
    location: str | None = None,
    severity: FindingSeverity = FindingSeverity.CONCERN,
) -> FindingInput:
    return FindingInput(severity=severity, summary=summary, location=location)


def verdict_input(
    verdict_id: str,
    node_id: str,
    *findings: FindingInput,
    **overrides: object,
) -> VerdictInput:
    """A stated CONCERNS whose findings parsed; ``overrides`` replace any field."""
    base = VerdictInput(
        id=verdict_id,
        node_id=node_id,
        verdict=ReviewVerdict.CONCERNS,
        derivation=VerdictDerivation.STATED,
        fallback_used=None,
        findings_parsed=True,
        provider_failure=False,
        review_type=REVIEW_TYPE,
        model="demo-model",
        findings=tuple(findings),
        provenance=PROVENANCE,
    )
    return dataclasses.replace(base, **overrides)  # pyright: ignore[reportArgumentType]


def provider_failure(verdict_id: str, node_id: str) -> VerdictInput:
    return verdict_input(
        verdict_id,
        node_id,
        verdict=ReviewVerdict.UNKNOWN,
        derivation=VerdictDerivation.NOT_REPORTED,
        findings_parsed=None,
        provider_failure=True,
    )


def _as_input(captured: CapturedFinding) -> FindingInput:
    return FindingInput(
        severity=parse_severity(captured.severity),
        summary=captured.summary,
        position_id=captured.position_id,
        category=captured.category,
        location=captured.location,
    )


def captured_verdict(verdict_id: str, node_id: str, path: Path) -> VerdictInput:
    """A ``VerdictInput`` built from a captured review file.

    ``derivation`` is the file's ``verdictSource`` (pinned ``stated`` on both
    part-1 files by the fixture guard test), or ``not_reported`` when the file
    has none. A *Provider Failure* heading marks a provider failure, whose
    findings were never parsed. Nothing is assumed beyond that.
    """
    frontmatter = read_frontmatter(path)
    source = frontmatter.get("verdictSource")
    failed = has_provider_failure_heading(path)
    return verdict_input(
        verdict_id,
        node_id,
        *(_as_input(captured) for captured in review_findings(path)),
        verdict=parse_verdict(str(frontmatter["verdict"])),
        derivation=(
            VerdictDerivation.NOT_REPORTED
            if source is None
            else VerdictDerivation(str(source))
        ),
        provider_failure=failed,
        findings_parsed=None if failed else True,
        model=str(frontmatter["aiModel"]),
        reviewed_sha=str(frontmatter["reviewedSha"]),
        tool_calls_made=frontmatter.get("toolCallsMade"),
        provenance=dataclasses.replace(PROVENANCE, source_path=path.name),
    )
