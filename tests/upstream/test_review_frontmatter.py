"""Frontmatter splitting and body-heading detection, through the public reader."""

from __future__ import annotations

from pathlib import Path

import pytest
from review_fixtures import (
    FINDINGS_NOT_PARSED_925,
    FINDINGS_NOT_PARSED_EDITED,
    PROVIDER_FAILURE_928,
    ROUND_1_PART_1,
    ROUND_2_PART_2,
    SQ_REVIEWS,
)

from amoeba.upstream.squadron.review import SquadronParseError
from amoeba.upstream.squadron.review_artifact import parse_review_artifact

_REAL_FILES = sorted(SQ_REVIEWS.glob("*.md"))


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


@pytest.mark.parametrize("path", _REAL_FILES, ids=lambda path: path.name[:50])
def test_every_real_file_yields_a_verdict(path: Path) -> None:
    assert _REAL_FILES  # a missing fixture directory must not pass vacuously
    assert parse_review_artifact(_text(path)).verdict is not None


@pytest.mark.parametrize(
    ("path", "provider_failure", "findings_parsed"),
    [
        (PROVIDER_FAILURE_928, True, True),
        (ROUND_2_PART_2, True, True),
        (FINDINGS_NOT_PARSED_925, False, False),
        (FINDINGS_NOT_PARSED_EDITED, False, False),
        (ROUND_1_PART_1, False, True),
    ],
)
def test_heading_flags_on_real_files(
    path: Path, provider_failure: bool, findings_parsed: bool
) -> None:
    parsed = parse_review_artifact(_text(path))
    assert parsed.provider_failure is provider_failure
    assert parsed.findings_parsed is findings_parsed


def test_leading_blank_lines_before_the_fence_are_allowed() -> None:
    parsed = parse_review_artifact("\n\n  \n" + _text(ROUND_1_PART_1))
    assert parsed.review_type == "tasks"


def test_trailing_spaces_on_a_fence_are_allowed() -> None:
    text = _text(ROUND_1_PART_1).replace("---\n", "---  \t\n", 2)
    assert parse_review_artifact(text).review_type == "tasks"


@pytest.mark.parametrize(
    "heading",
    ["# provider failure", "###### PROVIDER FAILURE  ", "##   Provider Failure"],
)
def test_a_provider_failure_heading_matches_at_any_level_and_case(heading: str) -> None:
    text = _text(ROUND_2_PART_2).replace("## Provider Failure", heading)
    assert heading in text
    assert parse_review_artifact(text).provider_failure is True


def test_a_findings_not_parsed_heading_matches_at_any_level_and_case() -> None:
    text = _text(FINDINGS_NOT_PARSED_925).replace(
        "## Findings Not Parsed", "#### findings NOT parsed"
    )
    assert "#### findings NOT parsed" in text
    assert parse_review_artifact(text).findings_parsed is False


def test_text_without_frontmatter_names_the_problem() -> None:
    with pytest.raises(SquadronParseError, match="no frontmatter"):
        parse_review_artifact("# not a review")


def test_malformed_yaml_chains_the_yaml_error() -> None:
    with pytest.raises(SquadronParseError, match="malformed YAML") as caught:
        parse_review_artifact("---\nverdict: [unclosed\n---\nbody\n")
    assert caught.value.__cause__ is not None


def test_frontmatter_that_is_not_a_mapping_is_rejected() -> None:
    with pytest.raises(SquadronParseError, match="not a mapping"):
        parse_review_artifact("---\n- one\n- two\n---\nbody\n")


def test_a_heading_quoted_inside_a_code_fence_is_not_a_heading() -> None:
    quoted = (
        _text(ROUND_1_PART_1)
        + "\n```\n## Provider Failure\n## Findings Not Parsed\n```\n"
    )
    parsed = parse_review_artifact(quoted)
    assert parsed.provider_failure is False
    assert parsed.findings_parsed is True
