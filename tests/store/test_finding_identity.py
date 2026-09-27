"""The finding matching rule: what it catches, and on real data, what it does not."""

from __future__ import annotations

from pathlib import Path

import pytest
from review_fixtures import (
    ROUND_1_PART_1,
    ROUND_1_PART_2,
    ROUND_2_PART_1,
    ROUND_2_PART_2,
    read_frontmatter,
    review_findings,
)

from amoeba.store.finding_identity import (
    RULE_VERSION,
    finding_identity,
    normalize_location,
    normalize_summary,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("plain text", "plain text"),
        ("  runs \t of\n\nwhitespace  ", "runs of whitespace"),
        ("the `KIND_EFFECTS` table", "the kind_effects table"),
        ("MiXeD CaSe", "mixed case"),
        ("Straße", "strasse"),
        ("ends with a period.", "ends with a period"),
        ("ends with a semicolon;", "ends with a semicolon"),
        ("ends with a colon:", "ends with a colon"),
        ("ends with a period .", "ends with a period"),
        ("ｆｕｌｌｗｉｄｔｈ", "fullwidth"),
        ("keeps inner. punctuation; intact", "keeps inner. punctuation; intact"),
    ],
)
def test_normalize_summary(raw: str, expected: str) -> None:
    assert normalize_summary(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, ""),
        ("", ""),
        ("   ", ""),
        ("unverified", ""),
        ("UNVERIFIED", ""),
        (" Unverified ", ""),
        ("src/a.py:12", "src/a.py"),
        ("src/a.py:12-30", "src/a.py"),
        ("src/a.py:12:4", "src/a.py"),
        ("src/a.py#L12", "src/a.py"),
        ("src/a.py#L12-L30", "src/a.py"),
        ("src/a.py, line 12", "src/a.py"),
        ("src/a.py, lines 12-30", "src/a.py"),
        ("tasks-2.md:34-37,55-58", "tasks-2.md"),
        ("see a.py:12 and b.py:40", "see a.py and b.py"),
        ("src\\amoeba\\store.py", "src/amoeba/store.py"),
        ("./src/a.py", "src/a.py"),
        ("slice.md#data-flow", "slice.md#data-flow"),
        ("src/Store.py", "src/Store.py"),
        ("  src/a.py   :12  ", "src/a.py"),
    ],
)
def test_normalize_location(raw: str | None, expected: str) -> None:
    assert normalize_location(raw) == expected


def test_location_case_is_kept() -> None:
    upper = finding_identity("src/Store.py", "x")
    assert upper != finding_identity("src/store.py", "x")


def test_key_is_hex_sha256() -> None:
    key = finding_identity("a.py", "summary")
    assert len(key) == 64
    int(key, 16)


def test_rule_version_is_one() -> None:
    assert RULE_VERSION == 1


@pytest.mark.parametrize(
    ("before", "after"),
    [
        (("tasks-2.md:119-163", "Same issue"), ("tasks-2.md:218-240", "Same issue")),
        (("src/a.py#L12", "Same issue"), ("src/a.py", "Same issue")),
        (("a.py", "The `x`  value."), ("a.py", "the x value")),
        (("unverified", "Same issue"), (None, "Same issue")),
    ],
)
def test_formatting_only_changes_keep_the_key(
    before: tuple[str | None, str], after: tuple[str | None, str]
) -> None:
    assert finding_identity(*before) == finding_identity(*after)


@pytest.mark.parametrize(
    ("before", "after"),
    [
        (("src/a.py:12", "Same issue"), ("src/b.py:12", "Same issue")),
        (("a.py", "The value is wrong"), ("a.py", "The value is missing")),
    ],
)
def test_different_path_or_words_change_the_key(
    before: tuple[str | None, str], after: tuple[str | None, str]
) -> None:
    assert finding_identity(*before) != finding_identity(*after)


def test_location_and_summary_cannot_be_shifted_between_fields() -> None:
    assert finding_identity("a b", "c") != finding_identity("a", "b c")


# Frontmatter checked 20260926 against the LLD's Technical Requirements table.
_CAPTURED: dict[Path, tuple[str, str, str | None]] = {
    ROUND_1_PART_1: ("CONCERNS", "bf6d292", "stated"),
    ROUND_1_PART_2: ("PASS", "bf6d292", "stated"),
    ROUND_2_PART_1: ("CONCERNS", "20b3d70", "stated"),
    ROUND_2_PART_2: ("UNKNOWN", "20b3d70", None),
}


@pytest.mark.parametrize("path", list(_CAPTURED), ids=lambda p: p.name)
def test_captured_fixture_matches_the_lld_table(path: Path) -> None:
    verdict, sha_prefix, verdict_source = _CAPTURED[path]
    assert path.is_file(), f"missing fixture {path.name}"
    frontmatter = read_frontmatter(path)
    assert frontmatter["verdict"] == verdict, f"{path.name}: verdict"
    assert str(frontmatter["reviewedSha"]).startswith(sha_prefix), f"{path.name}: sha"
    assert frontmatter.get("verdictSource") == verdict_source, f"{path.name}: source"


def test_captured_rounds_share_no_keys() -> None:
    """The rewording limit, pinned on real data.

    Between the two captured 102 task-review rounds Squadron reworded every
    carried-over finding. For example, round 1's "Every success criterion in the
    slice design traces to at least one task" came back in round 2 as "Every LLD
    success criterion traces to at least one task, and no task is scope creep".
    The rule only removes formatting, so these are different keys. Matching them
    is judgment and belongs to initiative 140; loosening the rule to make this
    test fail has to be a deliberate decision.
    """
    round_1 = review_findings(ROUND_1_PART_1)
    round_2 = review_findings(ROUND_2_PART_1)
    assert (len(round_1), len(round_2)) == (9, 7)

    round_1_keys = {finding_identity(f.location, f.summary) for f in round_1}
    round_2_keys = {finding_identity(f.location, f.summary) for f in round_2}
    assert len(round_1_keys) == 9
    assert len(round_2_keys) == 7
    assert round_1_keys.isdisjoint(round_2_keys)

    assert _REWORDED_ROUND_1 in {f.summary for f in round_1}
    assert _REWORDED_ROUND_2 in {f.summary for f in round_2}


_REWORDED_ROUND_1 = (
    "Every success criterion in the slice design traces to at least one task"
)
_REWORDED_ROUND_2 = (
    "Every LLD success criterion traces to at least one task, "
    "and no task is scope creep"
)
