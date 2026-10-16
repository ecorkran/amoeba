"""The real judge-template review artifact against ``parse_review_artifact``."""

from __future__ import annotations

from review_fixtures import JUDGE_REVIEW_107

from amoeba.store.evidence_models import ReviewVerdict, VerdictDerivation
from amoeba.upstream.squadron.review_artifact import parse_review_artifact

EXPECTED_CRITERIA = {
    "Architectural goal alignment": 90.0,
    "Boundaries and layer responsibilities": 88.0,
    "Scope discipline": 82.0,
    "Dependency direction and integration points": 90.0,
    "Failure modes and error handling": 78.0,
    "NFR restatement": 85.0,
    "Antipatterns and specification quality": 83.0,
}


def test_the_judge_review_parses_to_the_values_stated_in_the_file() -> None:
    parsed = parse_review_artifact(JUDGE_REVIEW_107.read_text(encoding="utf-8"))
    assert parsed.review_type == "judge.slice-vs-arch"
    assert parsed.verdict is ReviewVerdict.PASS
    assert parsed.score == 86.0
    assert parsed.model == "claude-sonnet-5-5"
    assert dict(parsed.criteria or {}) == EXPECTED_CRITERIA
    assert parsed.upstream_version == "0.22.0"
    assert parsed.sq_run_id == "run-20261016-judge-cycle-01714217"


def test_the_judge_review_carries_no_verdict_source() -> None:
    # Squadron states no verdictSource in a judge artifact, so the verdict is
    # recorded as not reported and its trust label is unattested.
    text = JUDGE_REVIEW_107.read_text(encoding="utf-8")
    assert "verdictSource" not in text
    parsed = parse_review_artifact(text)
    assert parsed.derivation is VerdictDerivation.NOT_REPORTED
