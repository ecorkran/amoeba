"""Passages (slice 143): cutting, selection, assembly, rendering, citations."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest
from purity import io_use

from amoeba.answering import passages
from amoeba.answering.passages import (
    CitationKind,
    CitationProblem,
    Passage,
    PassageKind,
    PassageSet,
    PlanRow,
    PmAnswer,
    ProgramSources,
    SourceFile,
    SourcesProblem,
    SourcesProblemKind,
    assemble,
    check_citations,
    cut_passages,
    format_utc,
    match_rules_entry,
    parse_git_date,
    render_passages,
    select_plan_files,
)

SOURCES = Path(__file__).parent / "fixtures" / "sources"


@pytest.mark.parametrize("fence", ["```", "~~~", "````"])
def test_a_heading_inside_a_code_fence_does_not_cut(fence: str) -> None:
    text = f"# Top\n{fence}\n# not a heading\n{fence}\nafter\n"

    assert cut_passages(text) == (text,)


def test_a_shorter_or_different_fence_does_not_close_a_fence() -> None:
    text = "# Top\n````\n```\n# inside\n~~~~\n````\n## Next\n"

    assert cut_passages(text) == (
        "# Top\n````\n```\n# inside\n~~~~\n````\n",
        "## Next\n",
    )


def test_a_level_four_heading_does_not_cut() -> None:
    text = "# Top\ntext\n#### Deep\nmore\n"

    assert cut_passages(text) == (text,)


def test_headings_of_levels_one_to_three_cut() -> None:
    text = "# One\na\n## Two\nb\n### Three\nc\n"

    assert cut_passages(text) == ("# One\na\n", "## Two\nb\n", "### Three\nc\n")


def test_front_matter_is_its_own_passage() -> None:
    text = "---\ndocType: x\n---\n\n# Title\nbody\n"

    assert cut_passages(text) == ("---\ndocType: x\n---\n\n", "# Title\nbody\n")


def test_a_file_without_headings_is_one_passage() -> None:
    assert cut_passages("plain\nrules\n") == ("plain\nrules\n",)


def test_an_empty_file_gives_no_passages() -> None:
    assert cut_passages("") == ()


def test_a_blank_preamble_is_dropped() -> None:
    assert cut_passages("\n  \n# Title\nbody\n") == ("# Title\nbody\n",)


@pytest.mark.parametrize(
    ("heading", "cuts"),
    [("   # Indented", True), ("    # Code block", False), ("#tag", False)],
)
def test_leading_spaces_and_a_missing_space_decide_whether_a_line_is_a_heading(
    heading: str, cuts: bool
) -> None:
    text = f"# Top\n{heading}\n"

    assert (len(cut_passages(text)) == 2) is cuts


def test_yaml_comments_inside_front_matter_are_not_headings() -> None:
    text = "---\n# a comment\ndocType: x\n---\n\n# Title\nbody\n"

    assert cut_passages(text) == (
        "---\n# a comment\ndocType: x\n---\n\n",
        "# Title\nbody\n",
    )


def test_a_leading_rule_line_without_a_closing_mark_is_not_front_matter() -> None:
    text = "---\n# Title\nbody\n"

    assert cut_passages(text) == ("---\n", "# Title\nbody\n")


def test_a_bare_hash_line_is_a_heading() -> None:
    assert cut_passages("# Top\n#\nx\n") == ("# Top\n", "#\nx\n")


def test_a_final_line_without_a_newline_is_kept() -> None:
    assert cut_passages("# A\n# B") == ("# A\n", "# B")


def test_crlf_text_survives_cutting() -> None:
    text = "# A\r\nbody\r\n## B\r\nmore\r\n"

    assert cut_passages(text) == ("# A\r\nbody\r\n", "## B\r\nmore\r\n")


def _fixture_files() -> list[Path]:
    return sorted(path for path in SOURCES.rglob("*") if path.is_file())


def test_the_fixture_directory_holds_the_frozen_files() -> None:
    assert len(_fixture_files()) == 9


@pytest.mark.parametrize("path", _fixture_files(), ids=lambda path: path.name)
def test_passages_of_a_real_file_join_back_to_it(path: Path) -> None:
    text = path.read_text()

    pieces = cut_passages(text)

    assert "".join(pieces) == text
    for piece in pieces[1:]:
        assert piece.lstrip(" ").startswith("#")


def test_the_passages_module_does_no_io() -> None:
    assert io_use(passages) == []


# Selection (D1, D10)

ROWS = (
    PlanRow("docs/arch", "{initiative}-arch.*.md", required=False),
    PlanRow("docs/slices", "{slice}-slice.*.md", required=True),
    PlanRow("docs/tasks", "{slice}-tasks.*.md", required=False),
)


@pytest.mark.parametrize(
    ("entry", "listing", "expected"),
    [
        ("CLAUDE.md", ["CLAUDE.md", "other.md"], ("CLAUDE.md",)),
        ("CLAUDE.md", ["other.md"], ()),
        ("rules/*.md", ["b.md", "a.md", "c.txt"], ("a.md", "b.md")),
        (
            "rules/py*on.md",
            ["python.md", "pyon.md", "pyton.txt"],
            ("pyon.md", "python.md"),
        ),
        ("rules/?.md", ["a.md", "?.md"], ("?.md",)),
        ("rules/[ab].md", ["a.md", "[ab].md"], ("[ab].md",)),
        ("a+b(1).md", ["a+b(1).md", "aab1.md"], ("a+b(1).md",)),
        ("a.md", ["aXmd"], ()),
    ],
)
def test_a_rules_entry_matches_by_its_last_segment_only(
    entry: str, listing: list[str], expected: tuple[str, ...]
) -> None:
    assert match_rules_entry(entry, listing) == expected


def test_plan_files_match_in_table_order_then_by_name() -> None:
    listings = {
        "docs/tasks": ["132-tasks.x-2.md", "132-tasks.x-1.md", "1320-tasks.y.md"],
        "docs/slices": ["132-slice.x.md", "133-slice.z.md"],
        "docs/arch": ["120-arch.a.md", "1200-arch.b.md"],
    }

    assert select_plan_files(ROWS, listings, 132, 120) == (
        "docs/arch/120-arch.a.md",
        "docs/slices/132-slice.x.md",
        "docs/tasks/132-tasks.x-1.md",
        "docs/tasks/132-tasks.x-2.md",
    )


def test_a_row_with_no_match_and_an_absent_directory_give_nothing() -> None:
    listings = {"docs/slices": ["132-slice.x.md"], "docs/tasks": ["99-tasks.x.md"]}

    assert select_plan_files(ROWS, listings, 132, 120) == (
        "docs/slices/132-slice.x.md",
    )


# Dates and rendering

FIXED = datetime(2026, 3, 4, 5, 6, 7, 999_000, tzinfo=timezone(timedelta(hours=2)))


def test_format_utc_converts_offsets_and_drops_sub_seconds() -> None:
    assert format_utc(FIXED) == "2026-03-04T03:06:07Z"


@pytest.mark.parametrize("text", ["", "  ", "not a date", "2026-03-04T05:06:07"])
def test_parse_git_date_gives_none_for_anything_unusable(text: str) -> None:
    assert parse_git_date(text) is None


def test_parse_git_date_reads_a_git_line() -> None:
    assert parse_git_date("2026-03-04T05:06:07+02:00\n") == FIXED.replace(microsecond=0)


def _passage(
    number: int, kind: PassageKind, text: str, date: datetime, **extra: str | None
) -> Passage:
    fields: dict[str, str | None] = {
        "source": None,
        "question": None,
        "slice_label": None,
        "question_id": None,
        "member": None,
    }
    fields.update(extra)
    return Passage(
        id=f"P{number}", kind=kind, source=fields["source"], date=date, text=text,
        question=fields["question"], slice_label=fields["slice_label"],
        question_id=fields["question_id"], member=fields["member"],
    )  # fmt: skip


def _fixed_set() -> PassageSet:
    return PassageSet(
        (
            _passage(
                1, PassageKind.RULE, "# Rules\nUse main.\n", FIXED, source="CLAUDE.md"
            ),
            _passage(
                2,
                PassageKind.PLAN,
                "# Slice\nDesign.\n",
                datetime(2026, 3, 5, tzinfo=UTC),
                source="project-documents/user/slices/9-slice.example.md",
            ),
            _passage(
                3,
                PassageKind.PM_ANSWER,
                "Use main.",
                datetime(2026, 3, 6, 12, 30, tzinfo=UTC),
                question="Which branch?",
                slice_label="9 Example",
                question_id="q1",
            ),
        ),
        "c0ffee",
        (),
    )


def test_render_equals_the_hand_written_file() -> None:
    expected = (SOURCES.parent / "expected_passages.md").read_text()

    assert render_passages(_fixed_set()) == expected


def test_an_empty_set_renders_as_the_empty_string() -> None:
    assert render_passages(PassageSet((), "c0ffee", ())) == ""


def test_a_passage_line_that_looks_like_a_heading_adds_no_id() -> None:
    sneaky = _passage(1, PassageKind.RULE, "## Passage P9\n", FIXED, source="x.md")

    assert PassageSet((sneaky,), "c", ()).ids == {"P1"}


# Assembly (D7)

SLICE = "9 Example"
OTHER = "7 Other"


def _file(path: str, text: str, kind: PassageKind = PassageKind.RULE) -> SourceFile:
    return SourceFile(path, kind, FIXED, text, member=None)


def _pm(record_id: str, slice_label: str, day: int, answer: str = "Yes.") -> PmAnswer:
    return PmAnswer(
        record_id, f"Q {record_id}?", answer, datetime(2026, 4, day, tzinfo=UTC),
        slice_label,
    )  # fmt: skip


CONCEPT = SourceFile(
    "docs/program-concept.md", PassageKind.PROGRAM_CONCEPT, FIXED,
    "# Program\nHow the projects fit.\n", member="trading-data",
)  # fmt: skip
MEMBER_LIST = SourceFile(
    "trading", PassageKind.PROGRAM_MEMBERS, FIXED,
    "Program: trading\nProjects in this program:\n- trading-data\n", member=None,
)  # fmt: skip
PROGRAM = ProgramSources(concept=CONCEPT, members=MEMBER_LIST)
#: Rules (two passages), plan (one), then the program's two, before any PM answer.
LEADING_PASSAGES = 5


def _assemble(
    answers: list[PmAnswer],
    max_chars: int = 100_000,
    *files: SourceFile,
    program: ProgramSources = PROGRAM,
) -> PassageSet | SourcesProblem:
    committed = files or (
        _file("r.md", "# A\none\n## B\ntwo\n"),
        _file("p.md", "plan\n", PassageKind.PLAN),
    )
    return assemble(
        committed, answers, program_sources=program,
        max_chars=max_chars, source_commit="c0ffee",
    )  # fmt: skip


def _set(result: PassageSet | SourcesProblem) -> PassageSet:
    assert isinstance(result, PassageSet)
    return result


def test_order_is_rules_plan_program_then_pm_with_gap_free_ids() -> None:
    result = _set(_assemble([_pm("q1", SLICE, 1)]))

    assert [(p.id, p.kind) for p in result.passages] == [
        ("P1", PassageKind.RULE),
        ("P2", PassageKind.RULE),
        ("P3", PassageKind.PLAN),
        ("P4", PassageKind.PROGRAM_CONCEPT),
        ("P5", PassageKind.PROGRAM_MEMBERS),
        ("P6", PassageKind.PM_ANSWER),
    ]
    assert result.source_commit == "c0ffee"
    assert result.ids == {"P1", "P2", "P3", "P4", "P5", "P6"}


def test_pm_answers_come_newest_first_whatever_their_slice_label() -> None:
    answers = [
        _pm("a", OTHER, 9),
        _pm("b", SLICE, 1),
        _pm("c", SLICE, 2),
        _pm("d", OTHER, 3),
    ]

    result = _set(_assemble(answers))

    assert [p.question_id for p in result.passages[LEADING_PASSAGES:]] == [
        "a",
        "d",
        "c",
        "b",
    ]


def test_ties_on_date_go_by_record_id() -> None:
    result = _set(_assemble([_pm("q2", SLICE, 1), _pm("q1", SLICE, 1)]))

    assert [p.question_id for p in result.passages[LEADING_PASSAGES:]] == ["q1", "q2"]


def test_committed_and_program_text_over_the_limit_is_too_large_with_both_numbers() -> (
    None
):
    result = _assemble([], 10)

    assert isinstance(result, SourcesProblem)
    assert result.kind is SourcesProblemKind.TOO_LARGE
    assert "10" in result.detail
    assert str(len(render_passages(_set(_assemble([]))))) in result.detail


def test_the_first_misfit_drops_itself_and_every_later_answer() -> None:
    big = _pm("big", SLICE, 3, "x" * 400)
    small = _pm("small", SLICE, 2)
    older = _pm("older", OTHER, 1)
    fit_one = len(render_passages(_set(_assemble([small])))) + 1

    result = _set(_assemble([older, small, big], fit_one))

    assert [p.question_id for p in result.passages[LEADING_PASSAGES:]] == []
    assert result.dropped_pm_answers == ("big", "small", "older")


def test_answers_that_fit_are_kept_and_the_rest_dropped_in_order() -> None:
    first, second, third = _pm("a", SLICE, 3), _pm("b", SLICE, 2), _pm("c", SLICE, 1)
    two = len(render_passages(_set(_assemble([first, second]))))

    result = _set(_assemble([third, second, first], two))
    rendered = render_passages(result)

    assert [p.question_id for p in result.passages[LEADING_PASSAGES:]] == ["a", "b"]
    assert result.dropped_pm_answers == ("c",)
    assert len(rendered) <= two
    assert "Q c?" not in rendered


# Citations (D8)


@pytest.mark.parametrize("cited", [[], ["  "], ["", " "]])
def test_nothing_cited_is_uncited(cited: list[str]) -> None:
    assert check_citations(cited, {"P1"}) == CitationProblem(CitationKind.UNCITED, ())


@pytest.mark.parametrize("cited", [["p3"], [" P3"], ["P3", "p3 "]])
def test_known_ids_in_any_case_or_with_spaces_pass(cited: list[str]) -> None:
    assert check_citations(cited, frozenset({"P3"})) is None


def test_unknown_ids_are_reported_once_each_in_cited_order() -> None:
    result = check_citations(["P9", "P3", "p7", "P9"], {"P3"})

    assert result == CitationProblem(CitationKind.UNKNOWN_IDS, ("P9", "P7"))
