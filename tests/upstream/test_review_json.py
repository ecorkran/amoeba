"""``parse_review_json`` against real captures, the derived rules, and each failure."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from review_fixtures import PAIR_ARTIFACT, PAIR_STDOUT, SQ_REVIEWS

from amoeba.store.evidence_models import (
    FindingSeverity,
    RecordSource,
    ReviewVerdict,
    VerdictDerivation,
    VerdictStanding,
    verdict_standing,
)
from amoeba.store.finding_identity import finding_identity
from amoeba.upstream.squadron.review import ParsedReview, SquadronParseError
from amoeba.upstream.squadron.review_artifact import parse_review_artifact
from amoeba.upstream.squadron.review_json import parse_review_json

CLEAN_PASS = SQ_REVIEWS / "stdout-slice-927-clean-pass.json"
CONCERNS = SQ_REVIEWS / "stdout-slice-104-concerns-glmflash.json"
S = FindingSeverity


def _capture(path: Path = CONCERNS) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _parse(payload: dict[str, Any]) -> ParsedReview:
    return parse_review_json(json.dumps(payload))


def _standing(parsed: ParsedReview) -> VerdictStanding:
    return verdict_standing(
        provider_failure=parsed.provider_failure,
        verdict=parsed.verdict,
        findings_parsed=parsed.findings_parsed,
        derivation=parsed.derivation,
    )


def test_the_clean_pass_capture_is_findings_parsed_and_stated() -> None:
    parsed = parse_review_json(CLEAN_PASS.read_text(encoding="utf-8"))
    assert parsed.verdict is ReviewVerdict.PASS
    assert parsed.findings == ()
    assert parsed.findings_parsed is True
    assert _standing(parsed) is VerdictStanding.STATED
    assert parsed.source is RecordSource.STDOUT_JSON


def test_the_concerns_capture_gives_its_findings_in_order() -> None:
    parsed = parse_review_json(CONCERNS.read_text(encoding="utf-8"))
    assert parsed.verdict is ReviewVerdict.CONCERNS
    assert parsed.review_type == "slice"
    assert parsed.model == "z-ai/glm-5.3-flash"
    assert parsed.tool_calls_made == 48
    assert [f.position_id for f in parsed.findings] == [
        f"F{n:03d}" for n in range(1, 12)
    ]
    assert tuple(f.severity for f in parsed.findings) == (
        (S.PASS,) * 2 + (S.CONCERN,) * 4 + (S.NOTE,) * 5
    )
    first = parsed.findings[0]
    assert first.category == "alignment"
    assert first.location is not None and first.location.endswith(
        "104-slice.findings-verdicts-and-provenance.md:138"
    )
    assert parsed.reviewed_sha is None and parsed.slice is None
    assert parsed.source_document is None


def test_a_trailing_saved_review_line_is_ignored() -> None:
    text = CONCERNS.read_text(encoding="utf-8")
    assert parse_review_json(text + "\nSaved review to /tmp/x.md\n") == (
        parse_review_json(text)
    )


@pytest.mark.parametrize(
    ("fallback_used", "verdict_source", "findings_parsed", "derivation"),
    [
        (True, "stated", False, VerdictDerivation.STATED),
        (True, None, False, VerdictDerivation.NOT_REPORTED),
        (True, "derived", True, VerdictDerivation.DERIVED),
        (False, "stated", True, VerdictDerivation.STATED),
    ],
)
def test_findings_parsed_follows_the_fallback_rule(
    fallback_used: bool,
    verdict_source: str | None,
    findings_parsed: bool,
    derivation: VerdictDerivation,
) -> None:
    payload = _capture() | {
        "fallback_used": fallback_used,
        "verdictSource": verdict_source,
    }
    parsed = _parse(payload)
    assert parsed.findings_parsed is findings_parsed
    assert parsed.derivation is derivation
    assert parsed.fallback_used is fallback_used


def test_findings_parsed_is_unknown_when_fallback_used_is_absent() -> None:
    payload = _capture()
    del payload["fallback_used"]
    parsed = _parse(payload)
    assert parsed.findings_parsed is None
    assert parsed.fallback_used is None


def test_a_derived_verdict_under_fallback_has_derived_standing() -> None:
    parsed = _parse(_capture() | {"fallback_used": True, "verdictSource": "derived"})
    assert _standing(parsed) is VerdictStanding.DERIVED


def test_requested_model_is_kept_only_on_a_substitution() -> None:
    base = _capture() | {"requested_model": "asked-for"}
    assert _parse(base | {"model_substituted": False}).requested_model is None
    assert _parse(base).requested_model is None
    assert _parse(base | {"model_substituted": True}).requested_model == "asked-for"


def test_squadron_version_and_run_id_are_read_when_present() -> None:
    parsed = _parse(_capture() | {"squadron_version": "9.9.9", "run_id": "run-x"})
    assert parsed.upstream_version == "9.9.9"
    assert parsed.sq_run_id == "run-x"
    assert _parse(_capture()).upstream_version is None


def test_text_with_no_json_object_is_rejected() -> None:
    with pytest.raises(SquadronParseError, match="no JSON object"):
        parse_review_json("Error: the provider timed out")


def test_a_json_object_without_a_verdict_names_the_key() -> None:
    with pytest.raises(SquadronParseError, match="verdict"):
        parse_review_json('{"error": {"message": "rate limited"}}')


def test_malformed_json_chains_the_decode_error() -> None:
    with pytest.raises(SquadronParseError, match="malformed JSON") as caught:
        parse_review_json('{"verdict": "PASS",')
    assert caught.value.__cause__ is not None


def test_an_unknown_severity_is_rejected() -> None:
    payload = _capture()
    payload["structured_findings"][0]["severity"] = "shaky"
    with pytest.raises(SquadronParseError, match="shaky"):
        _parse(payload)


@pytest.mark.parametrize("key", ["severity", "summary"])
def test_a_finding_missing_a_required_key_is_rejected(key: str) -> None:
    payload = _capture()
    del payload["structured_findings"][0][key]
    with pytest.raises(SquadronParseError, match=key):
        _parse(payload)


def test_stray_braces_before_the_object_do_not_hide_it() -> None:
    text = CONCERNS.read_text(encoding="utf-8")
    assert parse_review_json("using {braces} first\n" + text) == parse_review_json(text)


def test_the_captured_pair_agrees_between_file_and_stdout() -> None:
    from_file = parse_review_artifact(PAIR_ARTIFACT.read_text(encoding="utf-8"))
    from_stdout = parse_review_json(PAIR_STDOUT.read_text(encoding="utf-8"))
    assert _capture(PAIR_STDOUT)["template_name"] == from_file.review_type == "slice"
    assert from_stdout.review_type == from_file.review_type
    assert from_stdout.verdict is from_file.verdict is ReviewVerdict.CONCERNS
    assert from_stdout.model == from_file.model
    assert _keys(from_stdout) == _keys(from_file)
    assert len(_keys(from_file)) == 6


def _keys(parsed: ParsedReview) -> list[str]:
    return [finding_identity(f.location, f.summary) for f in parsed.findings]
