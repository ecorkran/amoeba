"""The text of ``add`` and ``rm``, exact (slice 229, D4 to D6, task 8.2)."""

from __future__ import annotations

from amoeba.cli.render.registration import render_registration
from amoeba.cli.render.text import COLUMNS
from amoeba.operations.set_up_models import (
    Change,
    ChangeSubject,
    ChangeVerb,
    MemberState,
    OpenQuestion,
    ProgramState,
    SetUpOutcome,
    SetUpProblem,
    SetUpProblemCode,
    SetUpResult,
    WorkingDirectory,
    WorkingDirectoryNotAProject,
)
from amoeba.store.vocabulary import RulesFrom

NAMES = {"id-core": "core", "id-lib": "lib"}
DEFAULTS = ("CLAUDE.md", "AGENTS.md")
WHY = '"<why it is closed>"'


def _member(
    project_id: str,
    rules_from: RulesFrom = RulesFrom.CONFIG_DEFAULT,
    rules: tuple[str, ...] = (),
) -> MemberState:
    return MemberState(
        project_id=project_id,
        name=NAMES.get(project_id, project_id),
        rules_paths=rules,
        rules_from=rules_from,
        authorize_allow=(),
        authorize_deny=(),
        depends_on=(),
    )


def _record(line: str) -> Change:
    """``<verb> <subject> <detail>`` as a record, for readable test cases."""
    verb, subject, detail = line.split(" ", 2)
    return Change(verb=ChangeVerb(verb), subject=ChangeSubject(subject), detail=detail)


def _applied(
    program: str, members: tuple[MemberState, ...], *changes: str
) -> SetUpResult:
    return SetUpResult(
        outcome=SetUpOutcome.APPLIED,
        change_records=tuple(_record(line) for line in changes),
        problems=(),
        program=ProgramState(program_id=program, concept=None, members=members),
        working_directory=None,
    )


def _rejected(
    *problems: SetUpProblem, working_directory: WorkingDirectory | None = None
) -> SetUpResult:
    return SetUpResult(
        outcome=SetUpOutcome.REJECTED,
        change_records=(),
        problems=problems,
        program=None,
        working_directory=working_directory,
    )


def _text(result: SetUpResult) -> str:
    return render_registration(result, default_rules=DEFAULTS)


def test_a_first_run_says_it_created_a_program_and_added_the_member() -> None:
    result = _applied(
        "core", (_member("core"),), "added program core", "added member core"
    )

    assert _text(result) == (
        "added\n"
        "  created program core\n"
        "  added member core\n"
        "    rules: default (CLAUDE.md, AGENTS.md)\n"
    )


def test_joining_a_program_that_exists_says_so() -> None:
    result = _applied("group", (_member("lib"),), "added member lib")

    assert _text(result) == (
        "added\n"
        "  added member lib to existing program group\n"
        "    rules: default (CLAUDE.md, AGENTS.md)\n"
    )


def test_a_changed_member_shows_its_named_rules() -> None:
    member = _member("id-core", RulesFrom.NAMED, ("CLAUDE.md", "docs/*.md"))
    result = _applied("group", (member,), "updated member core")

    assert _text(result) == (
        "changed\n  changed member core\n    rules: CLAUDE.md, docs/*.md\n"
    )


def test_a_member_with_named_empty_rules_says_none() -> None:
    member = _member("id-core", RulesFrom.NAMED, ())

    result = _applied("group", (member,), "updated member core")

    assert _text(result).endswith("    rules: none\n")


def test_dependency_and_concept_lines_use_names() -> None:
    result = _applied(
        "group",
        (),
        "updated program group",
        "added dependency core on lib (from_source)",
        "updated dependency core on lib (from_release)",
    )

    assert _text(result) == (
        "added\n"
        "  changed the concept of program group\n"
        "  added dependency core on lib (from_source)\n"
        "  changed dependency core on lib (from_release)\n"
    )


def test_removals_print_the_names_the_records_carry() -> None:
    result = _applied(
        "group",
        (),
        "removed pair lib -> core",
        "removed member core",
        "removed member gone",
    )

    assert _text(result) == (
        "removed\n"
        "  removed pair lib -> core\n"
        "  removed member core\n"
        "  removed member gone\n"
    )


def test_a_repeat_says_unchanged() -> None:
    result = SetUpResult(
        outcome=SetUpOutcome.UNCHANGED,
        change_records=(),
        problems=(),
        program=None,
        working_directory=None,
    )

    assert _text(result) == "unchanged\n"


def test_a_rejection_gives_one_line_per_problem() -> None:
    result = _rejected(
        SetUpProblem(
            code=SetUpProblemCode.UNKNOWN_PROVIDER, detail="members.0: lib is no member"
        ),
        SetUpProblem(
            code=SetUpProblemCode.SELF_DEPENDENCY, detail="members.0: core on itself"
        ),
    )

    assert _text(result) == (
        "rejected: unknown_provider: members.0: lib is no member\n"
        "rejected: self_dependency: members.0: core on itself\n"
    )


def test_not_a_project_prints_the_fix_as_whole_commands() -> None:
    result = _rejected(
        SetUpProblem(code=SetUpProblemCode.NOT_A_PROJECT, detail="no project here"),
        working_directory=WorkingDirectoryNotAProject(not_a_project="no project"),
    )

    assert _text(result) == (
        "rejected: not_a_project: no project here\n"
        "  to fix, run one of:\n"
        "    cf init\n"
        "    amoeba add --project NAME\n"
    )


def test_rm_outside_a_project_tells_you_to_name_the_member_not_to_add() -> None:
    result = _rejected(
        SetUpProblem(code=SetUpProblemCode.NOT_A_PROJECT, detail="no project here"),
        working_directory=WorkingDirectoryNotAProject(not_a_project="no project"),
    )

    text = render_registration(result, default_rules=DEFAULTS, removing=True)

    assert text == (
        "rejected: not_a_project: no project here\n"
        "  to fix, name the member:\n"
        "    amoeba rm NAME\n"
    )


def test_not_a_project_about_another_reference_offers_no_project_fix() -> None:
    result = _rejected(
        SetUpProblem(
            code=SetUpProblemCode.NOT_A_PROJECT,
            detail="members.0.depends_on.0.provider: Project 'x' not found.",
        )
    )

    assert _text(result) == (
        "rejected: not_a_project: members.0.depends_on.0.provider: Project 'x' not "
        "found.\n"
    )


def test_open_questions_print_the_keys_and_the_commands_that_clear_them() -> None:
    detail = (
        "remove.members.0: 'core' has open questions "
        "(run-1 at 2026-11-10T11:00:00+00:00, run-2 at 2026-11-10T12:00:00+00:00); "
        "`dismiss` or `answer` them first"
    )
    first, second = "2026-11-10T11:00:00+00:00", "2026-11-10T12:00:00+00:00"
    result = _rejected(
        SetUpProblem(
            code=SetUpProblemCode.MEMBER_HAS_OPEN_QUESTIONS,
            detail=detail,
            open_questions=(
                OpenQuestion(run_id="run-1", paused_at=first),
                OpenQuestion(run_id="run-2", paused_at=second),
            ),
        )
    )

    lines = _text(result).splitlines()

    assert lines[0].startswith("rejected: member_has_open_questions: remove.members.0")
    assert lines[1:] == [
        "  clear each open question first:",
        f"    run-1 at {first}",
        f'      amoeba answer run-1 --paused-at {first} --text "<your answer>"',
        f"      amoeba dismiss run-1 --paused-at {first} --reason {WHY}",
        f"    run-2 at {second}",
        f'      amoeba answer run-2 --paused-at {second} --text "<your answer>"',
        f"      amoeba dismiss run-2 --paused-at {second} --reason {WHY}",
    ]


def test_a_long_detail_is_cut_to_the_width() -> None:
    result = _rejected(SetUpProblem(code=SetUpProblemCode.MALFORMED, detail="x " * 200))

    first = _text(result).splitlines()[0]

    assert len(first) <= COLUMNS
    assert first.endswith("…")


def test_a_refusal_that_holds_the_way_on_is_wrapped_in_full_never_cut() -> None:
    """``name_taken`` and its kin name the remotes and the flags to give; the operator
    has nothing else to read them from, so the whole detail is shown (261 D7)."""
    way_on = "give a free name with `amoeba add --name NAME` or attach it"
    detail = (
        "member 'widget' has this name; " + "its origin is somewhere " * 12 + way_on
    )
    result = _rejected(SetUpProblem(code=SetUpProblemCode.NAME_TAKEN, detail=detail))

    lines = _text(result).splitlines()

    assert lines[0] == "rejected: name_taken:"
    assert all(len(line) <= COLUMNS for line in lines)
    assert "…" not in "\n".join(lines)
    assert " ".join(part.strip() for part in lines[1:]) == detail


def test_a_default_member_on_a_joined_machine_says_default_alone() -> None:
    result = _applied(
        "core", (_member("core"),), "added program core", "added member core"
    )

    text = render_registration(result, default_rules=None)

    assert text.endswith("    rules: default\n")
    assert "CLAUDE.md" not in text


def test_removing_a_concept_member_says_to_clear_the_concept_first() -> None:
    result = _rejected(
        SetUpProblem(
            code=SetUpProblemCode.CONCEPT_MEMBER_NOT_MEMBER,
            detail="remove.members.0: 'core' is the concept member",
        )
    )

    removing = render_registration(result, default_rules=DEFAULTS, removing=True)

    assert removing == (
        "rejected: concept_member_not_member: remove.members.0: 'core' is the concept "
        "member\n"
        "  clear the concept first, then remove the member:\n"
        "    amoeba rm --concept\n"
    )
    assert "rm --concept" not in _text(result)
