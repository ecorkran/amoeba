"""Optional (config default) rules entries against real git repos (slice 229, D8)."""

from __future__ import annotations

from pathlib import Path

from user_configs import user_config

from amoeba.answering.passages import SourcesProblemKind
from amoeba.answering.source_reads import SourceSelection
from amoeba.operations.member_answering import answering_for
from amoeba.store.models import MemberSettings
from amoeba.store.vocabulary import RulesFrom
from answering.rules_reads_support import (
    DEFAULT_ENTRIES,
    build_repo,
    default_choice,
    failing_on,
    locate,
    named_choice,
    problem_of,
    read,
    read_paths,
    selected_paths,
)

CLAUDE = "# Claude rules\n\nUse tabs.\n"
AGENTS = "# Agent rules\n\nBe brief.\n"


def test_both_default_entries_present_are_selected_in_entry_order(
    tmp_path: Path,
) -> None:
    repo = build_repo(tmp_path / "r", {"AGENTS.md": AGENTS, "CLAUDE.md": CLAUDE})

    assert selected_paths(locate(repo, default_choice())) == ["CLAUDE.md", "AGENTS.md"]


def test_a_default_selection_marks_its_files_optional(tmp_path: Path) -> None:
    repo = build_repo(tmp_path / "r", {"CLAUDE.md": CLAUDE})

    selection = locate(repo, default_choice())

    assert isinstance(selection, SourceSelection)
    assert [chosen.optional for chosen in selection.files] == [True]


def test_only_one_default_entry_present_reads_that_one(tmp_path: Path) -> None:
    repo = build_repo(tmp_path / "r", {"AGENTS.md": AGENTS})

    assert read_paths(read(repo, default_choice())) == ["AGENTS.md"]


def test_no_default_entry_present_is_sources_missing_naming_both(
    tmp_path: Path,
) -> None:
    repo = build_repo(tmp_path / "r", {"README.md": "x\n"})

    problem = problem_of(locate(repo, default_choice()), SourcesProblemKind.MISSING)

    assert problem.detail == "no rules file found; tried: CLAUDE.md, AGENTS.md"


def test_a_named_entry_that_matches_nothing_still_fails_the_selection(
    tmp_path: Path,
) -> None:
    repo = build_repo(tmp_path / "r", {"CLAUDE.md": CLAUDE})

    problem = problem_of(
        locate(repo, named_choice("CLAUDE.md", "AGENTS.md")),
        SourcesProblemKind.MISSING,
    )

    assert "AGENTS.md" in problem.detail


def test_a_named_choice_with_no_entries_reads_no_rules_and_is_not_declined(
    tmp_path: Path,
) -> None:
    repo = build_repo(tmp_path / "r", {"CLAUDE.md": CLAUDE})

    assert read_paths(read(repo, named_choice())) == []


def test_an_optional_entry_in_a_missing_subdirectory_is_skipped(
    tmp_path: Path,
) -> None:
    repo = build_repo(tmp_path / "r", {"CLAUDE.md": CLAUDE})

    selection = locate(repo, default_choice("docs/rules.md", "CLAUDE.md"))

    assert selected_paths(selection) == ["CLAUDE.md"]


def test_an_optional_entry_in_an_existing_subdirectory_is_read(
    tmp_path: Path,
) -> None:
    repo = build_repo(tmp_path / "r", {"docs/rules.md": CLAUDE})

    assert selected_paths(locate(repo, default_choice("docs/rules.md"))) == [
        "docs/rules.md"
    ]


def test_an_optional_glob_matching_nothing_in_an_existing_directory_is_skipped(
    tmp_path: Path,
) -> None:
    repo = build_repo(tmp_path / "r", {"docs/guide.md": CLAUDE, "CLAUDE.md": CLAUDE})

    selection = locate(repo, default_choice("docs/rules-*.md", "CLAUDE.md"))

    assert selected_paths(selection) == ["CLAUDE.md"]


def test_a_failing_ls_tree_is_unreadable_not_a_skipped_entry(tmp_path: Path) -> None:
    repo = build_repo(tmp_path / "r", {"CLAUDE.md": CLAUDE})

    result = locate(
        repo, default_choice("docs/rules.md", "CLAUDE.md"), failing_on("ls-tree")
    )

    problem = problem_of(result, SourcesProblemKind.UNREADABLE)
    assert "docs/rules.md" in problem.detail


def test_a_default_member_reads_the_configs_entries_as_they_are_at_the_time(
    tmp_path: Path,
) -> None:
    repo = build_repo(tmp_path / "r", {"CLAUDE.md": CLAUDE, "AGENTS.md": AGENTS})
    member = MemberSettings(
        project_id="m",
        rules_paths=(),
        authorize_allow=(),
        authorize_deny=(),
        rules_from=RulesFrom.CONFIG_DEFAULT,
    )
    config = user_config()
    edited = config.model_copy(update={"default_rules_paths": ("AGENTS.md",)})

    before = answering_for(member, config).settings.rules
    after = answering_for(member, edited).settings.rules

    assert before.entries == DEFAULT_ENTRIES
    assert read_paths(read(repo, before)) == ["CLAUDE.md", "AGENTS.md"]
    assert read_paths(read(repo, after)) == ["AGENTS.md"]


def test_a_named_entry_in_a_missing_subdirectory_is_missing_not_unreadable(
    tmp_path: Path,
) -> None:
    repo = build_repo(tmp_path / "r", {"CLAUDE.md": CLAUDE})

    problem = problem_of(
        locate(repo, named_choice("docs/rules.md")), SourcesProblemKind.MISSING
    )

    assert problem.detail == "rules entry 'docs/rules.md' matches no file"


def test_a_failing_ls_tree_is_unreadable_for_a_named_entry_too(tmp_path: Path) -> None:
    repo = build_repo(tmp_path / "r", {"docs/rules.md": CLAUDE})

    result = locate(repo, named_choice("docs/rules.md"), failing_on("ls-tree"))

    problem_of(result, SourcesProblemKind.UNREADABLE)
