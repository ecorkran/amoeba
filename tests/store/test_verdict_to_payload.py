"""``verdict_to_payload`` is the exact inverse of ``verdict_from_payload``."""

from __future__ import annotations

from typing import cast

from review_fixtures import ROUND_1_PART_1

from amoeba.store.evidence_models import (
    FindingInput,
    FindingSeverity,
    Provenance,
    RecordSource,
    ReviewVerdict,
    VerdictDerivation,
    VerdictInput,
)
from amoeba.store.verdict_payload import (
    FINDING_PAYLOAD_KEYS,
    VERDICT_FINDINGS,
    VERDICT_PAYLOAD_KEYS,
    verdict_from_payload,
    verdict_to_payload,
)
from amoeba.upstream.squadron import parse_review_artifact, to_verdict_input


def _minimal(**overrides: object) -> VerdictInput:
    fields: dict[str, object] = {
        "id": "v-1",
        "node_id": "n-1",
        "verdict": ReviewVerdict.PASS,
        "derivation": VerdictDerivation.NOT_REPORTED,
        "fallback_used": None,
        "findings_parsed": None,
        "provider_failure": False,
        "review_type": "slice",
        "model": "a-model",
        "findings": (),
        "provenance": Provenance(
            upstream="squadron",
            upstream_version="x",
            source=RecordSource.STDOUT_JSON,
        ),
    }
    return VerdictInput(**{**fields, **overrides})  # type: ignore[arg-type]


def _round_trip(verdict: VerdictInput) -> dict[str, object]:
    payload = verdict_to_payload(verdict)
    assert verdict_from_payload(verdict.id, payload) == verdict
    assert set(payload) == VERDICT_PAYLOAD_KEYS
    return payload


def test_a_fully_populated_verdict_round_trips() -> None:
    full = _minimal(
        verdict=ReviewVerdict.CONCERNS,
        derivation=VerdictDerivation.DERIVED,
        fallback_used=True,
        findings_parsed=False,
        diff_truncated=True,
        requested_model="asked",
        reviewed_sha="abc123",
        score=7.5,
        criteria={"clarity": 3, "nested": {"a": [1, 2]}},
        tool_calls_made=4,
        sq_run_id="run-1",
        journal_entry_id="j-1",
        provenance=Provenance(
            upstream="squadron",
            upstream_version="0.15.0",
            source=RecordSource.ARTIFACT_FRONTMATTER,
            source_path="/abs/review.md",
        ),
    )
    payload = _round_trip(full)
    assert payload["verdict"] == "CONCERNS"
    assert payload["source"] == "artifact_frontmatter"


def test_a_verdict_with_every_optional_field_none_round_trips() -> None:
    payload = _round_trip(_minimal())
    assert payload["criteria"] is None
    assert payload["findings"] == []


def test_several_findings_with_null_category_and_location_round_trip() -> None:
    findings = (
        FindingInput(severity=FindingSeverity.CONCERN, summary="one", position_id="F1"),
        FindingInput(
            severity=FindingSeverity.NOTE,
            summary="two",
            category="c",
            location="a.py:3",
        ),
        FindingInput(severity=FindingSeverity.PASS, summary="three"),
    )
    payload = _round_trip(_minimal(findings=findings))
    entries = cast(list[dict[str, object]], payload[VERDICT_FINDINGS])
    assert len(entries) == 3
    for entry in entries:
        assert set(entry) == FINDING_PAYLOAD_KEYS
    assert entries[0]["severity"] == "concern"
    assert entries[0]["category"] is None and entries[0]["location"] is None


def test_a_verdict_composed_from_a_real_fixture_round_trips() -> None:
    parsed = parse_review_artifact(ROUND_1_PART_1.read_text(encoding="utf-8"))
    composed = to_verdict_input(
        parsed, node_id="n-1", upstream_version="pre-stamp", source_path="/x.md"
    )
    assert len(composed.findings) == 9
    _round_trip(composed)
