"""The ``verdict`` submission kind through the envelope and ``apply_submission``.

Payloads go through ``build_envelope`` first, so the store receives exactly
what the running process hands it: the validated payload, dumped to a dict.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime

import pytest
from evidence_harness import PROJECT, seed_node

from amoeba.inbox.envelope import EnvelopeError, build_envelope
from amoeba.store import (
    FindingSeverity,
    QuarantineReason,
    ReviewVerdict,
    Store,
    SubmissionKind,
    SubmissionOutcome,
    SubmissionRecord,
    VerdictStanding,
)

SUBMITTED_AT = datetime(2026, 9, 27, 12, 0, tzinfo=UTC)

_FINDING = {"severity": "concern", "summary": "The flag rule", "location": "a.py:3"}


def _payload(node_id: str, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "node_id": node_id,
        "verdict": "CONCERNS",
        "derivation": "stated",
        "fallback_used": None,
        "findings_parsed": True,
        "provider_failure": False,
        "review_type": "tasks",
        "model": "demo-model",
        "findings": [_FINDING],
        "upstream": "squadron",
        "upstream_version": "0.14.0",
        "source": "artifact_frontmatter",
    }
    return payload | overrides


def _submit(
    store: Store, submission_id: str, payload: Mapping[str, object]
) -> SubmissionRecord:
    envelope = build_envelope(
        submission_id=submission_id,
        project_id=PROJECT,
        kind=SubmissionKind.VERDICT,
        submitted_by="judge",
        submitted_at=SUBMITTED_AT,
        payload=payload,
    )
    return store.apply_submission(
        submission_id=envelope.id,
        project_id=envelope.project_id,
        kind=envelope.kind,
        submitted_by=envelope.submitted_by,
        submitted_at=envelope.submitted_at,
        payload=envelope.payload,
    )


def test_a_valid_submission_is_applied_as_a_verdict_with_its_id(store: Store) -> None:
    node = seed_node(store)
    record = _submit(store, "sub-1", _payload(node))

    assert record.outcome is SubmissionOutcome.APPLIED
    verdict = store.verdict("sub-1")
    assert verdict is not None
    assert verdict.id == record.id
    assert verdict.verdict is ReviewVerdict.CONCERNS
    assert verdict.standing is VerdictStanding.STATED
    assert verdict.findings[0].severity is FindingSeverity.CONCERN
    assert verdict.provenance.upstream_version == "0.14.0"


def test_every_optional_field_arrives(store: Store) -> None:
    node = seed_node(store)
    _submit(
        store,
        "sub-1",
        _payload(
            node,
            score=82.5,
            criteria={"coverage": "high"},
            tool_calls_made=4,
            diff_truncated=False,
            requested_model="glmflash",
            reviewed_sha="abc",
            sq_run_id="run-1",
            source_path="r.md",
        ),
    )
    verdict = store.verdict("sub-1")
    assert verdict is not None
    assert (verdict.score, verdict.tool_calls_made) == (82.5, 4)
    assert verdict.criteria == {"coverage": "high"}
    assert verdict.diff_truncated is False
    assert verdict.provenance.source_path == "r.md"


def test_applying_again_changes_nothing(store: Store) -> None:
    node = seed_node(store)
    first = _submit(store, "sub-1", _payload(node))
    again = _submit(store, "sub-1", _payload(node, verdict="PASS"))

    assert again == first
    assert [v.id for v in store.verdicts(PROJECT)] == ["sub-1"]
    assert len(store.submissions(PROJECT)) == 1


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        (
            {"verdict": "UNKNOWN", "provider_failure": True, "findings_parsed": None},
            "cannot carry findings",
        ),
        (
            {"provider_failure": True, "findings": [], "findings_parsed": None},
            "must have verdict UNKNOWN",
        ),
        ({"node_id": "no-such-node"}, "no node"),
        ({"upstream_version": ""}, "upstream_version"),
    ],
)
def test_a_failed_check_is_rejected_with_a_reason(
    store: Store, overrides: dict[str, object], reason: str
) -> None:
    node = seed_node(store)
    record = _submit(store, "sub-1", _payload(node) | overrides)

    assert record.outcome is SubmissionOutcome.REJECTED
    assert record.reason is not None
    assert reason in record.reason
    assert store.verdicts(PROJECT) == []


def test_a_node_in_another_project_is_rejected(store: Store) -> None:
    node = seed_node(store, project_id="other")
    record = _submit(store, "sub-1", _payload(node))
    assert record.outcome is SubmissionOutcome.REJECTED


@pytest.mark.parametrize(
    "payload_change",
    [
        {"derivation": "guessed"},
        {"verdict": "MAYBE"},
        {"findings": [{"severity": "warning", "summary": "x"}]},
    ],
)
def test_an_unknown_word_fails_envelope_validation(
    store: Store, payload_change: dict[str, object]
) -> None:
    with pytest.raises(EnvelopeError) as raised:
        _submit(store, "sub-1", _payload(seed_node(store)) | payload_change)
    assert raised.value.reason is QuarantineReason.INVALID_PAYLOAD


@pytest.mark.parametrize("omitted", ["findings_parsed", "fallback_used", "derivation"])
def test_an_omitted_not_reported_field_fails_validation(
    store: Store, omitted: str
) -> None:
    payload = _payload(seed_node(store))
    del payload[omitted]
    with pytest.raises(EnvelopeError) as raised:
        _submit(store, "sub-1", payload)
    assert raised.value.reason is QuarantineReason.INVALID_PAYLOAD


def test_verdict_and_severity_are_accepted_in_any_case(store: Store) -> None:
    node = seed_node(store)
    findings = [
        {"severity": "CONCERN", "summary": "upper"},
        {"severity": "Note", "summary": "mixed"},
    ]
    record = _submit(
        store, "sub-1", _payload(node, verdict="concerns", findings=findings)
    )

    assert record.outcome is SubmissionOutcome.APPLIED
    verdict = store.verdict("sub-1")
    assert verdict is not None
    assert verdict.verdict is ReviewVerdict.CONCERNS
    assert [f.severity for f in verdict.findings] == [
        FindingSeverity.CONCERN,
        FindingSeverity.NOTE,
    ]
