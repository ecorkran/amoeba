"""``parse_review_artifact`` against every real review file, and each failure."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest
from review_fixtures import (
    FINDINGS_NOT_PARSED_925,
    FINDINGS_NOT_PARSED_EDITED,
    PAIR_ARTIFACT,
    PR_REVIEW_116,
    PROVIDER_FAILURE_928,
    ROUND_1_PART_1,
    ROUND_1_PART_2,
    ROUND_2_PART_1,
    ROUND_2_PART_2,
    SQ_REVIEWS,
    STAMPED_REVIEW_106,
)

from amoeba.store.evidence_models import (
    FindingSeverity,
    RecordSource,
    ReviewVerdict,
    VerdictDerivation,
)
from amoeba.upstream.squadron.review import ParsedReview, SquadronParseError
from amoeba.upstream.squadron.review_artifact import parse_review_artifact


def _parse(path: Path) -> ParsedReview:
    return parse_review_artifact(path.read_text(encoding="utf-8"))


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


S = FindingSeverity


@dataclass(frozen=True)
class Expected:
    path: Path
    verdict: ReviewVerdict
    derivation: VerdictDerivation
    findings_parsed: bool
    provider_failure: bool
    review_type: str
    severities: tuple[FindingSeverity, ...]
    first_summary: str | None = None
    first_location: str | None = None


# Written by reading each file, not by printing the parser's output.
_TASKS_102 = "project-documents/user/tasks/102-tasks.resident-process-and-recovery"
EXPECTED = [
    Expected(
        ROUND_1_PART_1,
        ReviewVerdict.CONCERNS,
        VerdictDerivation.STATED,
        True,
        False,
        "tasks",
        (S.CONCERN,) * 4 + (S.NOTE,) * 2 + (S.PASS,) * 3,
        "ExitCode vocabulary is consumed in Section 6 before Task 7.1 defines it",
        f"{_TASKS_102}-2.md:119-163",
    ),
    Expected(
        ROUND_1_PART_2,
        ReviewVerdict.PASS,
        VerdictDerivation.STATED,
        True,
        False,
        "tasks",
        (S.PASS,) * 4 + (S.CONCERN, S.NOTE),
        "All slice success criteria trace to tasks",
        f"{_TASKS_102}-2.md",
    ),
    Expected(
        ROUND_2_PART_1,
        ReviewVerdict.CONCERNS,
        VerdictDerivation.STATED,
        True,
        False,
        "tasks",
        (S.CONCERN,) * 2 + (S.PASS,) * 3 + (S.NOTE,) * 2,
        "The GRACE_EXPIRED exit criterion has no CLI-level test despite Task 6.4 "
        "deferring one to Task 7.3",
        f"{_TASKS_102}-2.md:218-240",
    ),
    Expected(
        ROUND_2_PART_2,
        ReviewVerdict.UNKNOWN,
        VerdictDerivation.NOT_REPORTED,
        True,
        True,
        "tasks",
        (),
    ),
    Expected(
        PROVIDER_FAILURE_928,
        ReviewVerdict.UNKNOWN,
        VerdictDerivation.NOT_REPORTED,
        True,
        True,
        "slice",
        (),
    ),
    Expected(
        FINDINGS_NOT_PARSED_925,
        ReviewVerdict.UNKNOWN,
        VerdictDerivation.NOT_REPORTED,
        False,
        False,
        "code",
        (),
    ),
    Expected(
        FINDINGS_NOT_PARSED_EDITED,
        ReviewVerdict.CONCERNS,
        VerdictDerivation.STATED,
        False,
        False,
        "tasks",
        (S.CONCERN,) * 4 + (S.NOTE,) * 2 + (S.PASS,) * 3,
    ),
    Expected(
        PR_REVIEW_116,
        ReviewVerdict.UNKNOWN,
        VerdictDerivation.NOT_REPORTED,
        False,
        False,
        "code",
        (),
    ),
    Expected(
        STAMPED_REVIEW_106,
        ReviewVerdict.CONCERNS,
        VerdictDerivation.STATED,
        True,
        False,
        "slice",
        (S.PASS,) * 2 + (S.CONCERN,) * 2 + (S.NOTE,) * 4,
        "Dependency set and integration points match the slice plan and prior slices",
        "project-documents/user/slices/"
        "106-slice.outbound-change-feed-and-detection-of-external-work.md#dependencies",
    ),
    Expected(
        PAIR_ARTIFACT,
        ReviewVerdict.CONCERNS,
        VerdictDerivation.STATED,
        True,
        False,
        "slice",
        (S.CONCERN,) * 3 + (S.NOTE,) * 3,
        "Judge-template stdout verdict is ingested as UNKNOWN with no handling",
        "project-documents/user/slices/"
        "105-slice.squadron-review-parser-and-ingest.md#Interfaces Required",
    ),
]


def test_the_table_covers_every_real_review_file() -> None:
    assert {row.path for row in EXPECTED} == set(SQ_REVIEWS.glob("*.md"))


@pytest.mark.parametrize("row", EXPECTED, ids=lambda row: row.path.name[:48])
def test_each_real_file_parses_to_the_values_read_from_it(row: Expected) -> None:
    parsed = _parse(row.path)
    assert parsed.verdict is row.verdict
    assert parsed.derivation is row.derivation
    assert parsed.findings_parsed is row.findings_parsed
    assert parsed.provider_failure is row.provider_failure
    assert parsed.review_type == row.review_type
    assert parsed.source is RecordSource.ARTIFACT_FRONTMATTER
    assert parsed.fallback_used is None
    assert tuple(f.severity for f in parsed.findings) == row.severities
    if row.first_summary is not None:
        first = parsed.findings[0]
        assert (first.summary, first.location) == (
            row.first_summary,
            row.first_location,
        )
        assert first.position_id == "F001"
        assert [f.position_id for f in parsed.findings] == [
            f"F{n:03d}" for n in range(1, len(row.severities) + 1)
        ]


def test_both_provider_failures_carry_no_findings() -> None:
    for path in (ROUND_2_PART_2, PROVIDER_FAILURE_928):
        parsed = _parse(path)
        assert parsed.provider_failure is True
        assert parsed.findings == ()


def test_the_928_file_carries_its_run_id_and_stamp() -> None:
    parsed = _parse(PROVIDER_FAILURE_928)
    assert parsed.sq_run_id == "run-20260927-slices-plan-c4a4a608"
    assert parsed.upstream_version == "0.14.0"
    assert parsed.model == "z-ai/glm-5.3-flash"


def test_the_pr_review_has_no_slice_and_ignores_its_pr_block() -> None:
    parsed = _parse(PR_REVIEW_116)
    assert parsed.slice is None
    assert parsed.source_document == "https://github.com/ecorkran/squadron/pull/116"


def test_the_106_file_carries_run_id_stamp_and_sha() -> None:
    parsed = _parse(STAMPED_REVIEW_106)
    assert parsed.sq_run_id == "run-20260928-slices-plan-a04bdb07"
    assert parsed.upstream_version == "0.15.0"
    assert parsed.reviewed_sha == "c4c6d2c9dc1f4c1683ceab8cdf90e1685f134b19"
    assert parsed.tool_calls_made == 7
    assert parsed.slice == "outbound-change-feed-and-detection-of-external-work"


def test_the_captured_pair_file_carries_its_stamp_and_no_run_id() -> None:
    parsed = _parse(PAIR_ARTIFACT)
    assert parsed.upstream_version == "0.21.9"
    assert parsed.sq_run_id is None
    assert parsed.reviewed_sha == "0c8a499b4df3639cbd9c2af1f6201c5cf920bdc2"


def test_a_file_without_a_stamp_or_run_id_reads_them_as_none() -> None:
    parsed = _parse(ROUND_1_PART_1)
    assert parsed.upstream_version is None
    assert parsed.sq_run_id is None


# --- Errors, built by mutating a copy of a real file's text -----------------

_BASE = _text(ROUND_1_PART_1)


def _mutated(old: str, new: str) -> str:
    assert old in _BASE, old
    return _BASE.replace(old, new, 1)


@pytest.mark.parametrize(
    ("key", "line"),
    [
        ("verdict", "verdict: CONCERNS\n"),
        ("reviewType", "reviewType: tasks\n"),
        ("aiModel", "aiModel: z-ai/glm-5.3\n"),
    ],
)
def test_a_missing_required_key_is_named(key: str, line: str) -> None:
    with pytest.raises(SquadronParseError, match=key):
        parse_review_artifact(_mutated(line, ""))


def test_a_finding_that_is_not_a_mapping_is_rejected() -> None:
    text = _mutated("findings:\n", "findings:\n  - just a string\n")
    with pytest.raises(SquadronParseError, match=r"findings\[0\] is not a mapping"):
        parse_review_artifact(text)


def test_a_finding_without_severity_is_rejected() -> None:
    text = _mutated("    severity: concern\n", "")
    with pytest.raises(SquadronParseError, match="severity"):
        parse_review_artifact(text)


def test_a_finding_without_summary_is_rejected() -> None:
    first_summary = next(
        line for line in _BASE.splitlines(keepends=True) if "    summary:" in line
    )
    with pytest.raises(SquadronParseError, match="summary"):
        parse_review_artifact(_mutated(first_summary, ""))


def test_an_unknown_severity_word_is_rejected() -> None:
    with pytest.raises(SquadronParseError, match="shaky"):
        parse_review_artifact(_mutated("severity: concern", "severity: shaky"))


def test_an_unknown_verdict_word_is_rejected() -> None:
    with pytest.raises(SquadronParseError, match="MAYBE"):
        parse_review_artifact(_mutated("verdict: CONCERNS", "verdict: MAYBE"))


def test_a_provider_failure_with_a_verdict_is_rejected() -> None:
    text = _mutated("verdict: CONCERNS\n", "verdict: CONCERNS\nproviderFailure: true\n")
    with pytest.raises(SquadronParseError, match="must have verdict UNKNOWN"):
        parse_review_artifact(text)


def test_a_provider_failure_with_findings_is_rejected() -> None:
    text = _mutated("verdict: CONCERNS\n", "verdict: UNKNOWN\nproviderFailure: true\n")
    with pytest.raises(SquadronParseError, match="cannot carry findings"):
        parse_review_artifact(text)


def test_unknown_keys_do_not_change_the_result() -> None:
    edited = (
        _mutated("findings:\n", "resolution: fixed\nresolvedBy: someone\nfindings:\n")
        + "\n## Response\n\nNoted.\n"
    )
    assert parse_review_artifact(edited) == parse_review_artifact(_BASE)
