"""Builders for verdict inputs, shared by the store, inbox, and CLI evidence tests."""

from __future__ import annotations

import dataclasses
from pathlib import Path

from amoeba.store import (
    CheckInput,
    CheckOutcome,
    FindingInput,
    FindingSeverity,
    NodeKind,
    ProgressInput,
    ProgressKind,
    Provenance,
    RecordSource,
    ReviewVerdict,
    Store,
    VerdictDerivation,
    VerdictInput,
    sql_evidence,
)
from amoeba.store.mapping_evidence import verdict_parameters
from amoeba.upstream.squadron import parse_review_artifact, to_verdict_input

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


def captured_verdict(verdict_id: str, node_id: str, path: Path) -> VerdictInput:
    """A ``VerdictInput`` built from a captured review file, through the parser.

    The captured 102 files predate Squadron's version stamp, so the label is
    supplied. Nothing else is assumed beyond what the parser reads.
    """
    return to_verdict_input(
        parse_review_artifact(path.read_text(encoding="utf-8")),
        node_id=node_id,
        record_id=verdict_id,
        upstream_version=UPSTREAM_VERSION,
        source_path=path.name,
    )


def pre_judge_verdict_insert(
    verdict: VerdictInput, project_id: str, recorded_at: str
) -> tuple[str, tuple[object, ...]]:
    """The verdict insert as it was before migration 007, for staging old stores.

    ``judge_invocation_id`` is the last insert column; a store below version 7
    has no such column, so both the column list and the parameters drop it.
    """
    columns = sql_evidence.VERDICT_INSERT_COLUMNS[:-1]
    statement = (
        f"INSERT INTO {sql_evidence.TABLE_VERDICTS} ({', '.join(columns)}) "
        f"VALUES ({', '.join('?' for _ in columns)})"
    )
    return statement, verdict_parameters(verdict, project_id, recorded_at)[:-1]


CHECK_PROVENANCE = Provenance(
    upstream="context-forge",
    upstream_version="1.2.3",
    source=RecordSource.COMMAND_OUTPUT,
)


def check_input(check_id: str, node_id: str, **overrides: object) -> CheckInput:
    """A passed check that examined three things; ``overrides`` replace any field."""
    base = CheckInput(
        id=check_id,
        node_id=node_id,
        name="cf check",
        outcome=CheckOutcome.PASSED,
        examined_count=3,
        provenance=CHECK_PROVENANCE,
    )
    return dataclasses.replace(base, **overrides)  # pyright: ignore[reportArgumentType]


def progress_input(progress_id: str, node_id: str) -> ProgressInput:
    return ProgressInput(
        id=progress_id,
        node_id=node_id,
        progress_kind=ProgressKind.DEVLOG,
        content={"entry": "did a thing"},
        provenance=CHECK_PROVENANCE,
    )
