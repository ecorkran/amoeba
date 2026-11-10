"""The member list and the concept read (slice 223 task 4.5; ported from slice 182).

A real temporary repository holds the concept; ``cf`` is replayed, ``git`` runs for
real.
"""

from __future__ import annotations

import subprocess
from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest
from git_repo import commit_file, git

from amoeba.answering.passages import (
    PassageKind,
    ProgramSources,
    SourceFile,
    SourcesProblem,
    SourcesProblemKind,
)
from amoeba.operations.program_sources import (
    member_list_date,
    member_list_text,
    without_path,
)
from operations.program_rig import (
    ASKING_MEMBER,
    CONCEPT_MEMBER,
    CONCEPT_PATH,
    CONCEPT_TEXT,
    PROGRAM_ID,
    REGISTERED,
    THIRD_MEMBER,
    ProgramRig,
    add_branch_with_concept,
    build_program_rig,
    member,
    program,
    three_members,
)

PREFIX = f"concept member {CONCEPT_MEMBER}"


def _sources(result: object) -> ProgramSources:
    assert isinstance(result, ProgramSources), result
    return result


def _concept(result: object) -> SourceFile:
    concept = _sources(result).concept
    assert concept is not None
    return concept


def _problem(result: object, kind: SourcesProblemKind) -> SourcesProblem:
    assert isinstance(result, SourcesProblem), result
    assert result.kind is kind, result
    return result


# The member list


def test_the_member_list_for_three_members_matches_the_design_example() -> None:
    text = member_list_text(program(), three_members(), ASKING_MEMBER)

    assert text == (
        "Program: trading\n"
        "Projects in this program:\n"
        "- trading-data (holds the program concept)\n"
        "- trading-engine (this question comes from this project)\n"
        "- trading-ui\n"
    )


def test_members_are_listed_in_project_id_order_whatever_the_input_order() -> None:
    shuffled = [member(THIRD_MEMBER), member(CONCEPT_MEMBER), member(ASKING_MEMBER)]

    assert member_list_text(program(), shuffled, THIRD_MEMBER) == member_list_text(
        program(), three_members(), THIRD_MEMBER
    )


def test_an_asker_that_holds_the_concept_gets_both_markers_on_one_line() -> None:
    text = member_list_text(program(), three_members(), CONCEPT_MEMBER)

    assert (
        "- trading-data (holds the program concept; "
        "this question comes from this project)\n"
    ) in text
    assert text.count("this question comes from this project") == 1


def test_a_program_with_no_concept_marks_only_the_asker() -> None:
    text = member_list_text(
        program(concept_member=None, concept_path=None), three_members(), ASKING_MEMBER
    )

    assert "holds the program concept" not in text
    assert "- trading-engine (this question comes from this project)\n" in text


@pytest.mark.parametrize(
    ("concept_member", "asker"),
    [(CONCEPT_MEMBER, "elsewhere"), ("elsewhere", CONCEPT_MEMBER)],
)
def test_an_unknown_asker_or_concept_member_is_a_programming_error(
    concept_member: str, asker: str
) -> None:
    with pytest.raises(ValueError, match="is not a member of program 'trading'"):
        member_list_text(program(concept_member=concept_member), three_members(), asker)


def test_the_date_is_the_latest_of_the_program_and_its_members() -> None:
    newest = datetime(2026, 11, 4, 9, tzinfo=UTC)
    members = [*three_members()[:2], member(THIRD_MEMBER, updated=newest)]

    assert member_list_date(program(), members) == newest


def test_the_date_is_the_programs_when_no_member_is_newer() -> None:
    assert member_list_date(program(), three_members()) == REGISTERED


# Success paths


def test_the_concept_file_carries_its_text_member_and_last_change_date(
    tmp_path: Path,
) -> None:
    rig = build_program_rig(tmp_path)

    concept = _concept(rig.read())

    assert concept.kind is PassageKind.PROGRAM_CONCEPT
    assert concept.path == CONCEPT_PATH
    assert concept.text == CONCEPT_TEXT
    assert concept.member == CONCEPT_MEMBER
    # The unrelated commit after it is later; the file's own commit dates it.
    assert concept.date == rig.concept_date


def test_the_member_list_marks_the_asker_and_the_concept_holder(
    tmp_path: Path,
) -> None:
    found = _sources(build_program_rig(tmp_path).read())

    assert found.members.kind is PassageKind.PROGRAM_MEMBERS
    assert found.members.path == PROGRAM_ID
    assert found.members.member is None
    assert f"- {CONCEPT_MEMBER} (holds the program concept)" in found.members.text
    assert f"- {ASKING_MEMBER} (this question comes from this project)" in (
        found.members.text
    )


def test_an_uncommitted_edit_and_an_untracked_file_do_not_appear(
    tmp_path: Path,
) -> None:
    rig = build_program_rig(tmp_path)
    (rig.repo_path / CONCEPT_PATH).write_text("## Edited, not committed\n")
    (rig.repo_path / "docs" / "untracked.md").write_text("## Untracked\n")

    assert _concept(rig.read()).text == CONCEPT_TEXT


def test_a_commit_made_after_the_commit_was_resolved_is_invisible(
    tmp_path: Path,
) -> None:
    rig = build_program_rig(tmp_path)
    landed: list[str] = []

    def land_after_resolution(argv: Sequence[str]) -> None:
        # The second git call is the first read after the commit was resolved.
        if argv[0] == "git" and len(rig.run.git_calls) == 2 and not landed:
            landed.append(
                commit_file(rig.repo_path, CONCEPT_PATH, "## New\n", "lands mid-read")
            )

    rig.run.fault = lambda argv: land_after_resolution(argv)

    assert _concept(rig.read()).text == CONCEPT_TEXT
    assert landed
    for call in rig.run.git_calls[1:]:
        assert any(rig.head in argument for argument in call), call


def test_the_concept_is_read_on_the_members_target_branch(tmp_path: Path) -> None:
    rig = build_program_rig(tmp_path)
    branch_text = "## Branch concept\nthe target branch says this\n"
    add_branch_with_concept(rig.repo_path, "feature", branch_text)
    rig.run.target = "feature"

    assert _concept(rig.read()).text == branch_text


def test_a_program_with_no_concept_reads_nothing_and_has_only_the_member_list(
    tmp_path: Path,
) -> None:
    rig = build_program_rig(tmp_path)
    rig.the_program = program(concept_member=None, concept_path=None)

    found = _sources(rig.read())

    assert found.concept is None
    assert "- trading-engine (this question comes from this project)" in (
        found.members.text
    )
    assert rig.run.calls == []


# Failures


def _with_concept_path(rig: ProgramRig, path: str) -> None:
    rig.the_program = replace(rig.the_program, concept_path=path)


def test_a_concept_file_absent_from_its_listing_is_missing_naming_both(
    tmp_path: Path,
) -> None:
    rig = build_program_rig(tmp_path)
    _with_concept_path(rig, "docs/not-there.md")

    problem = _problem(rig.read(), SourcesProblemKind.MISSING)

    assert CONCEPT_MEMBER in problem.detail
    assert "docs/not-there.md" in problem.detail


def test_a_missing_parent_directory_is_unreadable(tmp_path: Path) -> None:
    rig = build_program_rig(tmp_path)
    _with_concept_path(rig, "nodocs/program-concept.md")

    problem = _problem(rig.read(), SourcesProblemKind.UNREADABLE)

    assert problem.detail.startswith(f"{PREFIX}: ")


def test_a_non_utf8_concept_file_is_unreadable_and_named(tmp_path: Path) -> None:
    rig = build_program_rig(tmp_path)
    (rig.repo_path / CONCEPT_PATH).write_bytes(b"\xff\xfe\x00 not text \x80")
    git(rig.repo_path, "add", "-f", "--", CONCEPT_PATH)
    git(rig.repo_path, "commit", "-q", "-m", "binary concept")

    problem = _problem(rig.read(), SourcesProblemKind.UNREADABLE)

    assert CONCEPT_PATH in problem.detail
    assert problem.detail.startswith(f"{PREFIX}: ")


def test_a_concept_member_that_is_no_context_forge_project_is_missing(
    tmp_path: Path,
) -> None:
    rig = build_program_rig(tmp_path, project_known=False)

    problem = _problem(rig.read(), SourcesProblemKind.MISSING)

    assert PREFIX in problem.detail


def test_a_failing_cf_target_read_is_unreadable_with_the_prefix(
    tmp_path: Path,
) -> None:
    rig = build_program_rig(tmp_path)
    rig.run.fault = lambda argv: (
        subprocess.CompletedProcess(list(argv), 1, "cf broke", "")
        if argv[1] == "config"
        else None
    )

    problem = _problem(rig.read(), SourcesProblemKind.UNREADABLE)

    assert problem.detail.startswith(f"{PREFIX}: ")
    assert "config get" in problem.detail


def test_a_failing_git_show_of_the_file_is_unreadable_with_the_prefix(
    tmp_path: Path,
) -> None:
    rig = build_program_rig(tmp_path)
    rig.run.fault = lambda argv: (
        subprocess.CompletedProcess(list(argv), 128, "", "fatal: nope")
        if "show" in argv and argv[-1].endswith(f":{CONCEPT_PATH}")
        else None
    )

    problem = _problem(rig.read(), SourcesProblemKind.UNREADABLE)

    assert problem.detail.startswith(f"{PREFIX}: ")
    assert CONCEPT_PATH in problem.detail


@pytest.mark.parametrize("command", ["cf", "git"])
def test_a_timeout_on_either_command_is_unreadable_with_the_prefix(
    tmp_path: Path, command: str
) -> None:
    rig = build_program_rig(tmp_path)
    rig.run.fault = lambda argv: (
        subprocess.TimeoutExpired(list(argv), 1) if argv[0] == command else None
    )

    problem = _problem(rig.read(), SourcesProblemKind.UNREADABLE)

    assert problem.detail.startswith(f"{PREFIX}: ")


# Size and call order


def test_a_concept_over_the_limit_is_too_large(tmp_path: Path) -> None:
    rig = build_program_rig(tmp_path)

    problem = _problem(
        rig.read(max_chars=len(CONCEPT_TEXT) - 1), SourcesProblemKind.TOO_LARGE
    )

    assert CONCEPT_PATH in problem.detail
    assert PREFIX in problem.detail


def test_two_cf_calls_and_four_git_calls_in_the_documented_order(
    tmp_path: Path,
) -> None:
    rig = build_program_rig(tmp_path)

    _sources(rig.read())

    assert [call[1] for call in rig.run.cf_calls] == ["get", "config"]
    assert rig.run.git_calls == [
        ("git", "log", "-1", "--format=%H", "main"),
        ("git", "show", f"{rig.head}:docs"),
        ("git", "log", "-1", "--format=%cI", rig.head, "--", CONCEPT_PATH),
        ("git", "show", f"{rig.head}:{CONCEPT_PATH}"),
    ]


# The asker holds the concept


def _own_file(path: str, kind: PassageKind) -> SourceFile:
    return SourceFile(path, kind, datetime(2026, 1, 1, tzinfo=UTC), CONCEPT_TEXT, None)


def test_a_concept_the_asker_already_read_is_relabelled_with_no_call(
    tmp_path: Path,
) -> None:
    own = (
        _own_file("CLAUDE.md", PassageKind.RULE),
        _own_file(CONCEPT_PATH, PassageKind.RULE),
    )
    rig = build_program_rig(tmp_path, asker_holds_concept=True, asker_files=own)

    concept = _concept(rig.read())

    assert concept.kind is PassageKind.PROGRAM_CONCEPT
    assert concept.member == CONCEPT_MEMBER
    assert concept.path == CONCEPT_PATH
    assert rig.run.calls == []
    assert [f.path for f in without_path(own, CONCEPT_PATH)] == ["CLAUDE.md"]


def test_a_concept_not_among_the_askers_files_is_read_at_its_pinned_commit(
    tmp_path: Path,
) -> None:
    rig = build_program_rig(tmp_path, asker_holds_concept=True)
    commit_file(rig.repo_path, CONCEPT_PATH, "## After\nnot seen\n", "after the pin")

    concept = _concept(rig.read())

    assert concept.text == CONCEPT_TEXT
    assert concept.member == CONCEPT_MEMBER
    assert rig.run.cf_calls == []
    assert len(rig.run.git_calls) == 3
    for call in rig.run.git_calls:
        assert any(rig.head in argument for argument in call), call
    assert ("git", "log", "-1", "--format=%H", "main") not in rig.run.git_calls


def test_without_path_removes_exactly_the_named_file_and_keeps_the_order() -> None:
    files = tuple(_own_file(f"{name}.md", PassageKind.PLAN) for name in "abc")

    assert [f.path for f in without_path(files, "b.md")] == ["a.md", "c.md"]
    assert without_path(files, "z.md") == files
