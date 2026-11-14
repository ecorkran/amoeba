"""Duplicate rule sections are dropped before numbering and counting (slice 229, D9)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from amoeba.answering.passages import (
    PassageKind,
    PassageSet,
    ProgramSources,
    SourceFile,
    SourcesProblem,
    SourcesProblemKind,
    assemble,
    cut_passages,
)
from amoeba.answering.rule_dedup import RuleDeduper
from amoeba.answering.source_reads import CommittedSources
from answering.rules_reads_support import (
    build_repo,
    default_choice,
    problem_of,
    read,
)

RULES_REPO = Path(__file__).parent / "fixtures" / "rules_repo"
CLAUDE = (RULES_REPO / "CLAUDE.md").read_text(encoding="utf-8")
AGENTS = (RULES_REPO / "AGENTS.md").read_text(encoding="utf-8")
FIXED = datetime(2026, 4, 1, tzinfo=UTC)
NO_PROGRAM = ProgramSources(
    concept=None,
    members=SourceFile(
        "demo", PassageKind.PROGRAM_MEMBERS, FIXED, "Program: demo\n", None
    ),
)


def _file(path: str, text: str, kind: PassageKind = PassageKind.RULE) -> SourceFile:
    return SourceFile(path, kind, FIXED, text, member=None)


def _assembled(*files: SourceFile) -> PassageSet:
    result = assemble(
        files, [], program_sources=NO_PROGRAM, max_chars=1_000_000, source_commit="c0"
    )
    assert isinstance(result, PassageSet), result
    return result


def _texts(passage_set: PassageSet, source: str) -> list[str]:
    return [p.text for p in passage_set.passages if p.source == source]


def test_the_helper_drops_a_rule_piece_an_earlier_file_held() -> None:
    deduper = RuleDeduper()

    first = deduper.new_pieces(is_rule=True, pieces=("a", "b"))
    second = deduper.new_pieces(is_rule=True, pieces=("b", "c"))

    assert (first, second) == (("a", "b"), ("c",))


def test_the_helper_keeps_a_repeat_inside_one_file() -> None:
    assert RuleDeduper().new_pieces(is_rule=True, pieces=("a", "a")) == ("a", "a")


def test_the_helper_never_drops_or_counts_a_non_rule_piece() -> None:
    deduper = RuleDeduper()

    plan_first = deduper.new_pieces(is_rule=False, pieces=("a",))
    rule_after = deduper.new_pieces(is_rule=True, pieces=("a",))
    plan_again = deduper.new_pieces(is_rule=False, pieces=("a",))

    assert (plan_first, rule_after, plan_again) == (("a",), ("a",), ("a",))


def test_shared_sections_appear_once_under_claude_and_agents_only_ones_stay() -> None:
    claude_pieces = cut_passages(CLAUDE)
    agents_pieces = cut_passages(AGENTS)
    shared = [piece for piece in agents_pieces if piece in claude_pieces]
    agents_only = [piece for piece in agents_pieces if piece not in claude_pieces]
    assert sum(len(piece) for piece in shared) > 10_000  # the fixture is a real copy

    result = _assembled(_file("CLAUDE.md", CLAUDE), _file("AGENTS.md", AGENTS))

    assert _texts(result, "CLAUDE.md") == list(claude_pieces)
    assert _texts(result, "AGENTS.md") == agents_only
    assert agents_only, "AGENTS.md has sections of its own"
    all_texts = [p.text for p in result.passages]
    assert all(all_texts.count(piece) == 1 for piece in shared)


def test_passage_numbers_stay_contiguous_after_dropping() -> None:
    result = _assembled(_file("CLAUDE.md", CLAUDE), _file("AGENTS.md", AGENTS))

    numbers = [int(p.id.removeprefix("P")) for p in result.passages]
    assert numbers == list(range(1, len(numbers) + 1))


def test_a_section_edited_in_one_file_stays_in_both() -> None:
    claude = "# Rules\nintro\n## Shared\nsame\n## Edited\nversion one\n"
    agents = "# Rules\nintro\n## Shared\nsame\n## Edited\nversion two\n"

    result = _assembled(_file("CLAUDE.md", claude), _file("AGENTS.md", agents))

    assert _texts(result, "AGENTS.md") == ["## Edited\nversion two\n"]
    assert _texts(result, "CLAUDE.md")[-1] == "## Edited\nversion one\n"


def test_a_plan_passage_equal_to_a_rule_passage_is_kept() -> None:
    section = "## Limits\nKeep files short.\n"

    result = _assembled(
        _file("CLAUDE.md", section),
        _file("plan.md", section, PassageKind.PLAN),
        _file("AGENTS.md", section),
    )

    committed = [
        p for p in result.passages if p.kind is not PassageKind.PROGRAM_MEMBERS
    ]
    assert [(p.source, p.kind) for p in committed] == [
        ("CLAUDE.md", PassageKind.RULE),
        ("plan.md", PassageKind.PLAN),
    ]


def _real_rules_repo(tmp_path: Path) -> Path:
    return build_repo(tmp_path / "r", {"CLAUDE.md": CLAUDE, "AGENTS.md": AGENTS})


def test_a_selection_that_fits_only_once_duplicates_are_dropped_is_not_too_large(
    tmp_path: Path,
) -> None:
    repo = _real_rules_repo(tmp_path)
    deduped = read(repo, default_choice())
    assert isinstance(deduped, CommittedSources)
    assert deduped.chars < len(CLAUDE) + len(AGENTS)

    fits = read(repo, default_choice(), max_chars=deduped.chars)
    too_small = read(repo, default_choice(), max_chars=deduped.chars - 1)

    assert isinstance(fits, CommittedSources)
    assert isinstance(too_small, SourcesProblem)
    assert too_small.kind is SourcesProblemKind.TOO_LARGE
    assert len(CLAUDE) + len(AGENTS) > deduped.chars  # raw text would have tripped


def test_the_counted_text_equals_the_numbered_text(tmp_path: Path) -> None:
    committed = read(_real_rules_repo(tmp_path), default_choice())
    assert isinstance(committed, CommittedSources)

    numbered = _assembled(*committed.files)

    counted = sum(len(p.text) for p in numbered.passages if p.kind is PassageKind.RULE)
    assert committed.chars == counted


def test_an_over_limit_set_still_reports_the_deduplicated_size(tmp_path: Path) -> None:
    repo = _real_rules_repo(tmp_path)

    problem = problem_of(
        read(repo, default_choice(), max_chars=100), SourcesProblemKind.TOO_LARGE
    )

    assert "the limit is 100" in problem.detail
