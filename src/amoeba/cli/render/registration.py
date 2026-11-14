"""The text of ``add`` and ``rm`` (slice 229, D4 to D6): one renderer for both.

The first line says what happened: ``added``, ``removed``, ``changed``,
``unchanged``, or one ``rejected: <code>: <detail>`` per problem. Then one line per
change, written from the engine's change lines (defined once in ``set_up_models``)
with Context Forge names for ids, and each changed member's rules. Two refusals say
how to go on: a working directory that is no Context Forge project prints the fix
(only then: a ``not_a_project`` about another reference gets none), a member with
open questions prints the commands that clear them, and removing a concept's member
says to clear the concept first. Commands are never cut.
"""

from __future__ import annotations

from collections.abc import Mapping

from amoeba.cli.render.commands import (
    NOT_A_PROJECT_FIXES,
    answer_command,
    clear_concept_command,
    dismiss_command,
    rm_member_command,
)
from amoeba.cli.render.text import command_line, indented, prose_line, rules_text
from amoeba.operations.set_up_models import (
    ChangeSubject,
    ChangeVerb,
    OpenQuestion,
    SetUpOutcome,
    SetUpProblem,
    SetUpProblemCode,
    SetUpResult,
    WorkingDirectoryNotAProject,
)
from amoeba.store.models import QuestionKey
from amoeba.store.vocabulary import RulesFrom


def render_registration(
    result: SetUpResult,
    *,
    names: Mapping[str, str],
    default_rules: tuple[str, ...],
    removing: bool = False,
) -> str:
    """The text of one ``add`` or ``rm`` result.

    Args:
        names: Context Forge project names by id; an id with no name prints as itself.
        default_rules: The config's ``default_rules_paths``, for a default member.
        removing: The result is ``rm``'s, so a refusal can say how to remove.
    """
    if result.outcome is SetUpOutcome.REJECTED:
        lines = _rejection(
            result.problems,
            names=names,
            removing=removing,
            offer_project_fix=isinstance(
                result.working_directory, WorkingDirectoryNotAProject
            ),
        )
    elif result.outcome is SetUpOutcome.UNCHANGED:
        lines = ["unchanged"]
    else:
        lines = [_headline(result), *_changes(result, names, default_rules)]
    return "\n".join(lines) + "\n"


def _headline(result: SetUpResult) -> str:
    """``added`` when anything was added, ``removed`` when only removals happened,
    else ``changed``."""
    verbs = {record.verb for record in result.change_records}
    if ChangeVerb.ADDED in verbs:
        return "added"
    if verbs == {ChangeVerb.REMOVED}:
        return "removed"
    return "changed"


def _named(text: str, names: Mapping[str, str]) -> str:
    for project_id, name in names.items():
        text = text.replace(project_id, name)
    return text


def _changes(
    result: SetUpResult, names: Mapping[str, str], default_rules: tuple[str, ...]
) -> list[str]:
    changes = result.change_records
    created = any(
        change.verb is ChangeVerb.ADDED and change.subject is ChangeSubject.PROGRAM
        for change in changes
    )
    program = None if result.program is None else result.program.program_id
    members = (
        {}
        if result.program is None
        else {member.project_id: member for member in result.program.members}
    )
    lines: list[str] = []
    for change in changes:
        detail = _named(change.detail, names)
        match (change.verb, change.subject):
            case (ChangeVerb.ADDED, ChangeSubject.PROGRAM):
                lines.append(indented(f"created program {detail}"))
            case (ChangeVerb.UPDATED, ChangeSubject.PROGRAM):
                lines.append(indented(f"changed the concept of program {detail}"))
            case (verb, ChangeSubject.MEMBER) if verb is not ChangeVerb.REMOVED:
                lines.append(indented(_member_line(verb, detail, created, program)))
                member = members.get(change.detail)
                if member is not None:
                    default = member.rules_from is RulesFrom.CONFIG_DEFAULT
                    rules = rules_text(
                        default_rules if default else member.rules_paths,
                        default=default,
                    )
                    lines.append(indented(f"rules: {rules}", 2))
            case (ChangeVerb.UPDATED, subject):
                lines.append(indented(f"changed {subject.value} {detail}"))
            case (verb, subject):
                lines.append(indented(f"{verb.value} {subject.value} {detail}"))
    return lines


def _member_line(
    verb: ChangeVerb, detail: str, program_created: bool, program: str | None
) -> str:
    if verb is ChangeVerb.UPDATED:
        return f"changed member {detail}"
    if program_created or program is None:
        return f"added member {detail}"
    return f"added member {detail} to existing program {program}"


def _rejection(
    problems: tuple[SetUpProblem, ...],
    *,
    names: Mapping[str, str],
    removing: bool,
    offer_project_fix: bool,
) -> list[str]:
    lines: list[str] = []
    for problem in problems:
        lines.append(
            prose_line(
                f"rejected: {problem.code.value}: ", _named(problem.detail, names)
            )
        )
    for problem in problems:
        match problem.code:
            case SetUpProblemCode.NOT_A_PROJECT if offer_project_fix and removing:
                lines.append(indented("to fix, name the member:"))
                lines.append(command_line(rm_member_command()))
            case SetUpProblemCode.NOT_A_PROJECT if offer_project_fix:
                lines.append(indented("to fix, run one of:"))
                lines.extend(command_line(fix) for fix in NOT_A_PROJECT_FIXES)
            case SetUpProblemCode.MEMBER_HAS_OPEN_QUESTIONS:
                lines.extend(_open_question_help(problem.open_questions))
            case SetUpProblemCode.CONCEPT_MEMBER_NOT_MEMBER if removing:
                lines.append(
                    indented("clear the concept first, then remove the member:")
                )
                lines.append(command_line(clear_concept_command()))
            case _:
                pass
    return lines


def _open_question_help(questions: tuple[OpenQuestion, ...]) -> list[str]:
    lines = [indented("clear each open question first:")]
    for question in questions:
        key = QuestionKey(question.run_id, question.paused_at)
        lines.append(indented(f"{key.run_id} at {key.paused_at}", 2))
        lines.append(command_line(answer_command(key), 3))
        lines.append(command_line(dismiss_command(key), 3))
    return lines
