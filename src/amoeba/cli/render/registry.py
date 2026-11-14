"""The text of ``list programs``, ``list members`` and ``list dependencies`` (229 D3).

Blocks and lines, no table: a path is never cut, so it sits on its own line, and every
other line is held to 100 columns. A member Context Forge gives no path says
``(no path in Context Forge)``; one it no longer lists shows its id and
``(not in Context Forge)``.
"""

from __future__ import annotations

from typing import Final

from amoeba.cli.render.text import (
    NONE,
    SEPARATOR,
    command_line,
    indented,
    prose_line,
    rules_text,
)
from amoeba.operations.list_registry import (
    DependenciesView,
    MemberRow,
    MembersView,
    ProgramsView,
)
from amoeba.store.vocabulary import RulesFrom

NO_PATH: Final = "(no path in Context Forge)"
NOT_IN_CF: Final = "(not in Context Forge)"
NO_PROGRAMS: Final = "No programs."
NO_MEMBERS: Final = "No members."
NO_DEPENDENCIES: Final = "No dependencies."


def render_programs(view: ProgramsView) -> str:
    if not view.programs:
        return NO_PROGRAMS + "\n"
    lines: list[str] = []
    for row in view.programs:
        lines.append(row.program)
        if row.concept is not None:
            lines.append(
                prose_line(
                    indented("concept: "), f"{row.concept.member} ({row.concept.path})"
                )
            )
        if not row.members:
            lines.append(indented(f"members: {NONE}"))
        else:
            lines.append(indented("members:"))
            lines.extend(indented(member, 2) for member in row.members)
    return "\n".join(lines) + "\n"


def render_members(view: MembersView) -> str:
    if not view.members:
        return NO_MEMBERS + "\n"
    names = {row.project_id: row.name for row in view.members if row.name}
    blocks = ["\n".join(_member_block(row, names)) for row in view.members]
    return "\n\n".join(blocks) + "\n"


def _member_block(row: MemberRow, names: dict[str, str]) -> list[str]:
    title = row.name if row.in_context_forge and row.name else row.project_id
    marker = "" if row.in_context_forge else f" {NOT_IN_CF}"
    lines = [prose_line("", f"{title}{marker}{SEPARATOR}program {row.program}")]
    if row.in_context_forge:
        if row.path is None:
            lines.append(indented(f"path: {NO_PATH}"))
        else:
            lines.extend([indented("path:"), command_line(row.path)])
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
    lines.extend(
        prose_line(
            indented("depends on: "),
            f"{_end(names.get(dep.provider), dep.provider)} ({dep.consumed.value})",
        )
        for dep in row.depends_on
    )
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


def _end(name: str | None, project_id: str) -> str:
    return name if name is not None else f"{project_id} {NOT_IN_CF}"
