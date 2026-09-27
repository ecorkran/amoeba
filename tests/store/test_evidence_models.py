"""Evidence vocabularies, parse rules, record types, and the trust label table."""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime
from enum import StrEnum

import pytest

from amoeba.store.evidence_models import (
    COMPARABLE_STANDINGS,
    FindingChange,
    FindingChanges,
    FindingInput,
    FindingObservation,
    FindingSeverity,
    FindingSummary,
    Provenance,
    RecordSource,
    ReviewVerdict,
    TaggedFinding,
    VerdictDerivation,
    VerdictInput,
    VerdictRecord,
    VerdictStanding,
    parse_severity,
    parse_verdict,
    verdict_standing,
)


@pytest.mark.parametrize(
    ("vocabulary", "members"),
    [
        (ReviewVerdict, {"PASS", "CONCERNS", "FAIL", "UNKNOWN"}),
        (FindingSeverity, {"pass", "note", "concern", "fail"}),
        (VerdictDerivation, {"stated", "derived", "imposed", "not_reported"}),
        (RecordSource, {"stdout_json", "artifact_frontmatter"}),
        (FindingChange, {"new", "recurring", "gone"}),
        (
            VerdictStanding,
            {
                "provider_failure",
                "unparsed",
                "findings_unparsed",
                "imposed",
                "derived",
                "unattested",
                "stated",
            },
        ),
    ],
)
def test_vocabulary_members(vocabulary: type[StrEnum], members: set[str]) -> None:
    assert {member.value for member in vocabulary} == members


def test_comparable_standings() -> None:
    assert {
        VerdictStanding.STATED,
        VerdictStanding.DERIVED,
        VerdictStanding.IMPOSED,
        VerdictStanding.UNATTESTED,
    } == COMPARABLE_STANDINGS


@pytest.mark.parametrize("text", ["pass", "PASS", "Pass", " concerns ", "Fail"])
def test_parse_verdict_accepts_any_case(text: str) -> None:
    assert parse_verdict(text) is ReviewVerdict(text.strip().upper())


@pytest.mark.parametrize("text", ["concern", "note", "CONCERN", "Fail", "PASS"])
def test_parse_severity_accepts_any_case(text: str) -> None:
    assert parse_severity(text) is FindingSeverity(text.lower())


@pytest.mark.parametrize("text", ["PASSED", "concern", "", "ok"])
def test_parse_verdict_rejects_unknown_words(text: str) -> None:
    with pytest.raises(ValueError, match="unknown verdict"):
        parse_verdict(text)


@pytest.mark.parametrize("text", ["concerns", "warning", "", "critical"])
def test_parse_severity_rejects_unknown_words(text: str) -> None:
    with pytest.raises(ValueError, match="unknown severity"):
        parse_severity(text)


_V = ReviewVerdict
_D = VerdictDerivation
_S = VerdictStanding


@pytest.mark.parametrize(
    ("provider_failure", "verdict", "findings_parsed", "derivation", "expected"),
    [
        (True, _V.UNKNOWN, None, _D.NOT_REPORTED, _S.PROVIDER_FAILURE),
        # Precedence: every later row also matches, provider failure still wins.
        (True, _V.UNKNOWN, False, _D.DERIVED, _S.PROVIDER_FAILURE),
        (False, _V.UNKNOWN, True, _D.STATED, _S.UNPARSED),
        (False, _V.CONCERNS, False, _D.STATED, _S.FINDINGS_UNPARSED),
        (False, _V.CONCERNS, False, _D.DERIVED, _S.FINDINGS_UNPARSED),
        (False, _V.CONCERNS, True, _D.IMPOSED, _S.IMPOSED),
        (False, _V.PASS, True, _D.DERIVED, _S.DERIVED),
        (False, _V.PASS, None, _D.NOT_REPORTED, _S.UNATTESTED),
        # Table coverage only: Squadron cannot produce a CONCERNS with zero
        # findings and findings_parsed=true today (it sets fallback_used).
        (False, _V.CONCERNS, True, _D.STATED, _S.STATED),
        (False, _V.PASS, None, _D.STATED, _S.STATED),
    ],
)
def test_verdict_standing_table(
    provider_failure: bool,
    verdict: ReviewVerdict,
    findings_parsed: bool | None,
    derivation: VerdictDerivation,
    expected: VerdictStanding,
) -> None:
    standing = verdict_standing(
        provider_failure=provider_failure,
        verdict=verdict,
        findings_parsed=findings_parsed,
        derivation=derivation,
    )
    assert standing is expected


def test_every_standing_is_produced_by_the_table() -> None:
    produced = {
        verdict_standing(
            provider_failure=pf, verdict=v, findings_parsed=fp, derivation=d
        )
        for pf in (True, False)
        for v in ReviewVerdict
        for fp in (True, False, None)
        for d in VerdictDerivation
    }
    assert produced == set(VerdictStanding)


def _record() -> VerdictRecord:
    return VerdictRecord(
        id="v1",
        node_id="n1",
        verdict=ReviewVerdict.PASS,
        derivation=VerdictDerivation.DERIVED,
        fallback_used=True,
        findings_parsed=True,
        provider_failure=False,
        review_type="tasks",
        model="m",
        findings=(),
        provenance=Provenance(
            upstream="squadron",
            upstream_version="0.14.0",
            source=RecordSource.STDOUT_JSON,
        ),
        project_id="p",
        recorded_seq=1,
        recorded_at=datetime(2026, 9, 27, tzinfo=UTC),
    )


def test_record_standing_reads_the_label_function() -> None:
    assert _record().standing is VerdictStanding.DERIVED


_OBSERVATION = FindingObservation(
    verdict_id="v1",
    ordinal=0,
    severity=FindingSeverity.NOTE,
    summary="s",
    position_id="F001",
    category=None,
    location=None,
    normalized_location="",
    normalized_summary="s",
    identity="k",
    identity_version=1,
)


@pytest.mark.parametrize(
    "instance",
    [
        Provenance(upstream="u", upstream_version="1", source=RecordSource.STDOUT_JSON),
        FindingInput(severity=FindingSeverity.NOTE, summary="s"),
        _record(),
        _OBSERVATION,
        FindingSummary(
            node_id="n",
            identity="k",
            identity_version=1,
            latest_severity=FindingSeverity.NOTE,
            latest_summary="s",
            latest_location=None,
            first_verdict_id="v1",
            last_verdict_id="v1",
            times_seen=1,
        ),
        TaggedFinding(observation=_OBSERVATION, change=FindingChange.NEW),
        FindingChanges(
            verdict_id="v1",
            comparable=True,
            previous_verdict_id=None,
            findings=(),
            gone=(),
        ),
    ],
    ids=lambda instance: type(instance).__name__,
)
def test_every_record_type_is_frozen(instance: object) -> None:
    field = next(iter(vars(instance)))
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(instance, field, "changed")


def test_verdict_input_requires_explicit_not_reported_fields() -> None:
    required = {
        f.name
        for f in dataclasses.fields(VerdictInput)
        if f.default is dataclasses.MISSING and f.default_factory is dataclasses.MISSING
    }
    assert {"derivation", "fallback_used", "findings_parsed"} <= required
