"""The text of ``list programs``, ``list members`` and ``list dependencies`` (229 D3),
and ``list standing`` (230 D4).

Blocks and lines, no table: a path is never cut, so it sits on its own line, and every
other line is held to 100 columns. A member shows its name, id, program, ``origin``,
settings and checkouts (261 D13); one with no checkout is marked, and one named by its
id says how to give it a name.
"""

from __future__ import annotations

from typing import Final

from amoeba.cli.render.standing import reach_text
from amoeba.cli.render.text import (
    NONE,
    SEPARATOR,
    command_line,
    indented,
    prose_line,
    rules_text,
    wrapped,
)
from amoeba.cli.render.waking import TIME_FORMAT
from amoeba.operations.list_registry import (
    DependenciesView,
    MemberRow,
    MembersView,
    ProgramsView,
    StandingRow,
    StandingView,
)
from amoeba.store.vocabulary import RulesFrom

NO_CHECKOUT: Final = "(no checkout)"
NAMED_BY_ID: Final = "(named by its id)"
NO_PROGRAMS: Final = "No programs."
NO_MEMBERS: Final = "No members."
NO_DEPENDENCIES: Final = "No dependencies."
NO_STANDING: Final = "No standing answers."


def render_programs(view: ProgramsView) -> str:
    if not view.programs:
        return NO_PROGRAMS + "\n"
    lines: list[str] = []
    for row in view.programs:
        lines.append(row.program)
        if row.concept is not None:
            lines.append(
                prose_line(
                    indented("concept: "),
                    f"{_end(row.names.get(row.concept.member), row.concept.member)}"
                    f" ({row.concept.path})",
                )
            )
        if not row.members:
            lines.append(indented(f"members: {NONE}"))
        else:
            lines.append(indented("members:"))
            lines.extend(
                indented(_end(row.names.get(member), member), 2)
                for member in row.members
            )
    return "\n".join(lines) + "\n"


def render_members(view: MembersView) -> str:
    if not view.members:
        return NO_MEMBERS + "\n"
    names = {row.project_id: row.name for row in view.members}
    blocks = ["\n".join(_member_block(row, names)) for row in view.members]
    return "\n\n".join(blocks) + "\n"


def _member_block(row: MemberRow, names: dict[str, str]) -> list[str]:
    markers = [
        marker
        for marker, applies in (
            (NO_CHECKOUT, not row.checkouts),
            (NAMED_BY_ID, row.name == row.project_id),
        )
        if applies
    ]
    suffix = "".join(f" {marker}" for marker in markers)
    lines = [prose_line("", f"{row.name}{suffix}{SEPARATOR}program {row.program}")]
    lines.append(indented(f"id: {row.project_id}"))
    lines.append(indented(f"origin: {row.origin if row.origin else NONE}"))
    lines.append(
        prose_line(
            indented("rules: "),
            rules_text(
                row.rules_paths, default=row.rules_from is RulesFrom.CONFIG_DEFAULT
            ),
        )
    )
    for label, keys in (("allow", row.authorize_allow), ("deny", row.authorize_deny)):
        if keys:
            lines.append(prose_line(indented(f"{label}: "), ", ".join(keys)))
    if row.wake_command is not None:
        lines.extend([indented("wake command:"), command_line(row.wake_command)])
    lines.extend(
        prose_line(
            indented("depends on: "),
            f"{names.get(dep.provider, dep.provider)} ({dep.consumed.value})",
        )
        for dep in row.depends_on
    )
    lines.extend(_checkout_lines(row))
    if row.name == row.project_id:
        lines.append(indented("to give it a name:"))
        lines.append(command_line(f"amoeba add --project {row.project_id} --name NAME"))
    return lines


def _checkout_lines(row: MemberRow) -> list[str]:
    if not row.checkouts:
        return [indented(f"checkouts: {NONE}")]
    lines = [indented("checkouts:")]
    for checkout in row.checkouts:
        lines.append(
            indented(
                f"{checkout.machine}, Context Forge id {checkout.cf_project_id}", 2
            )
        )
        lines.append(command_line(checkout.path, 3))
        if checkout.wake_command is not None:
            lines.append(indented("wake command:", 3))
            lines.append(command_line(checkout.wake_command, 4))
    return lines


def render_dependencies(view: DependenciesView) -> str:
    if not view.dependencies:
        return NO_DEPENDENCIES + "\n"
    lines = [
        prose_line(
            "",
            f"{_end(row.provider_name, row.provider_id)} -> "
            f"{_end(row.consumer_name, row.consumer_id)} ({row.consumed.value})",
        )
        for row in view.dependencies
    ]
    return "\n".join(lines) + "\n"


def render_standing_view(view: StandingView) -> str:
    """One block per standing answer, newest first; the text is wrapped to the
    width, never cut."""
    if not view.standing:
        return NO_STANDING + "\n"
    blocks = ["\n".join(_standing_block(row)) for row in view.standing]
    return "\n\n".join(blocks) + "\n"


def _standing_block(row: StandingRow) -> list[str]:
    member = None if row.member is None else _end(row.member_name, row.member)
    reach = reach_text(row.reach, row.program, member)
    given = row.given_at.strftime(TIME_FORMAT)
    lines = [f"#{row.standing_id}{SEPARATOR}{reach}{SEPARATOR}{given}"]
    lines.extend(wrapped(row.text))
    if row.withdrawn_at is not None:
        if row.withdraw_reason is None:
            raise ValueError(
                f"standing answer {row.standing_id} has no withdraw reason"
            )
        withdrawn = row.withdrawn_at.strftime(TIME_FORMAT)
        lines.append(
            prose_line(indented(f"withdrawn {withdrawn}: "), row.withdraw_reason)
        )
    return lines


def _end(name: str | None, project_id: str) -> str:
    """The name; a reach with no member name (a program row) prints the id."""
    return name if name is not None else project_id
