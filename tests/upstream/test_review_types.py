"""The parsed-review value and its error classes."""

from __future__ import annotations

import dataclasses

import pytest

from amoeba.store.evidence_models import (
    RecordSource,
    ReviewVerdict,
    VerdictDerivation,
)
from amoeba.upstream.squadron.review import (
    ParsedReview,
    SquadronParseError,
    SquadronReviewError,
    UpstreamVersionError,
)


def _parsed() -> ParsedReview:
    return ParsedReview(
        verdict=ReviewVerdict.PASS,
        derivation=VerdictDerivation.STATED,
        fallback_used=None,
        findings_parsed=True,
        provider_failure=False,
        review_type="slice",
        model="a-model",
        requested_model=None,
        diff_truncated=None,
        reviewed_sha=None,
        tool_calls_made=None,
        score=None,
        criteria=None,
        sq_run_id=None,
        findings=(),
        source=RecordSource.ARTIFACT_FRONTMATTER,
        upstream_version=None,
        slice=None,
        source_document=None,
    )


def test_parsed_review_is_frozen() -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        _parsed().model = "other"  # type: ignore[misc]


def test_parsed_review_rejects_positional_construction() -> None:
    with pytest.raises(TypeError):
        ParsedReview(ReviewVerdict.PASS)  # type: ignore[call-arg]


def test_every_error_is_a_value_error() -> None:
    parse_error = SquadronParseError(RecordSource.STDOUT_JSON, "missing 'verdict'")
    for error in (SquadronReviewError("x"), parse_error, UpstreamVersionError("x")):
        assert isinstance(error, ValueError)
    assert parse_error.source is RecordSource.STDOUT_JSON
    assert "missing 'verdict'" in str(parse_error)


def test_version_error_is_not_a_parse_error() -> None:
    assert not issubclass(UpstreamVersionError, SquadronParseError)
    assert issubclass(UpstreamVersionError, SquadronReviewError)
