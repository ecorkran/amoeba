"""Pydantic payload models for the ``verdict`` submission kind.

Field names are the payload keys defined once in ``amoeba.store.verdict_payload``;
a test pins the two together. Enum fields use the store's word lists. Verdict
and severity are accepted in any letter case; any other unknown word fails
validation, so the file is quarantined and never reaches the store.

``derivation``, ``fallback_used``, and ``findings_parsed`` have no default: a
submitter says ``not_reported`` or ``null`` rather than leaving them out.
"""

from __future__ import annotations

from pydantic import BaseModel, field_validator

from amoeba.inbox.payload_config import MODEL_CONFIG
from amoeba.store.evidence_models import (
    FindingSeverity,
    RecordSource,
    ReviewVerdict,
    VerdictDerivation,
    parse_severity,
    parse_verdict,
)


class FindingPayload(BaseModel):
    """One finding as the reviewer gave it."""

    model_config = MODEL_CONFIG

    severity: FindingSeverity
    summary: str
    position_id: str | None = None
    category: str | None = None
    location: str | None = None

    @field_validator("severity", mode="before")
    @classmethod
    def _any_case_severity(cls, value: object) -> object:
        return parse_severity(value) if isinstance(value, str) else value


class VerdictPayload(BaseModel):
    """One review result; the submission id becomes the record id."""

    model_config = MODEL_CONFIG

    node_id: str
    verdict: ReviewVerdict
    derivation: VerdictDerivation
    fallback_used: bool | None
    findings_parsed: bool | None
    provider_failure: bool
    review_type: str
    model: str
    findings: list[FindingPayload]
    upstream: str
    upstream_version: str
    source: RecordSource
    source_path: str | None = None
    diff_truncated: bool | None = None
    requested_model: str | None = None
    reviewed_sha: str | None = None
    score: float | None = None
    criteria: dict[str, object] | None = None
    tool_calls_made: int | None = None
    sq_run_id: str | None = None
    journal_entry_id: str | None = None

    @field_validator("verdict", mode="before")
    @classmethod
    def _any_case_verdict(cls, value: object) -> object:
        return parse_verdict(value) if isinstance(value, str) else value
