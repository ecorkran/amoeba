"""The program's own passages: the member list and the concept file (slice 223, D11).

The member list is worded from values (slice 182, D4). The concept is one file from
one other repository, the one the program record names, read through the git
allowlist at that member's target (182, D3); it never selects that member's rules or
plan and never reads its PM answers (182, D6). When the asking project holds the
concept, its own pinned commit is used and no ``cf`` call is made. A program with no
concept gives a member list alone. A result is a value or a ``SourcesProblem``.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Final

from amoeba.answering.passages import (
    PassageKind,
    ProgramSources,
    SourceFile,
    SourcesProblem,
    SourcesProblemKind,
    unreadable,
)
from amoeba.answering.source_reads import (
    GitReads,
    Listings,
    SelectedFile,
    in_context,
    read_file,
)
from amoeba.store.models import Member, Program
from amoeba.upstream.context_forge.cli_call import CfCallFailed, CfRun
from amoeba.upstream.context_forge.project_of import CFProjectNotFound, project_of
from amoeba.upstream.context_forge.target_read import ReadFailure, read_target
from amoeba.upstream.git_read import GitReadResult, resolve_commit_args

#: The fixed marker words in the member list (182, D4), defined once.
CONCEPT_HOLDER_MARKER: Final = "holds the program concept"
ASKER_MARKER: Final = "this question comes from this project"
_MARKER_JOINER: Final = "; "


def member_list_text(
    program: Program, members: Sequence[Member], asking_project: str
) -> str:
    """The member list passage's text: the program, then its projects by id.

    The concept member (when the program has one) and the asking project are marked
    in parentheses; one project that is both gets both markers on its one line.

    Raises:
        ValueError: ``asking_project`` or the program's concept member is not among
            ``members`` (a programming error: registration prevents it).
    """
    ids = sorted(member.project_id for member in members)
    needed = [("asking project", asking_project)]
    if program.concept_member is not None:
        needed.append(("concept member", program.concept_member))
    for role, project_id in needed:
        if project_id not in ids:
            raise ValueError(
                f"{role} {project_id!r} is not a member of program "
                f"{program.program_id!r}"
            )
    lines = [f"Program: {program.program_id}", "Projects in this program:"]
    for project_id in ids:
        markers = [
            marker
            for marker, applies in (
                (CONCEPT_HOLDER_MARKER, project_id == program.concept_member),
                (ASKER_MARKER, project_id == asking_project),
            )
            if applies
        ]
        suffix = f" ({_MARKER_JOINER.join(markers)})" if markers else ""
        lines.append(f"- {project_id}{suffix}")
    return "\n".join(lines) + "\n"


def member_list_date(program: Program, members: Sequence[Member]) -> datetime:
    """The latest ``updated_at`` of the program and its members."""
    return max([program.updated_at, *(member.updated_at for member in members)])


@dataclass(frozen=True)
class AskerReads:
    """The asking project's own checkout and pinned commit, used when it holds the
    concept (182, D3)."""

    checkout: Path
    commit: str
    files: tuple[SourceFile, ...]


@dataclass(frozen=True)
class ProgramRead:
    """What the program read needs besides the program and its members."""

    asker: Member
    asker_reads: AskerReads
    #: Characters still allowed for the concept text after the project's own text.
    #: An early stop on raw text (182, D5); assembly decides on rendered size.
    max_chars: int
    run: CfRun
    timeout_seconds: float


def read_program_sources(
    program: Program, members: Sequence[Member], read: ProgramRead
) -> ProgramSources | SourcesProblem:
    """The member list and, when the program has a concept, the concept file."""
    members_file = SourceFile(
        path=program.program_id,
        kind=PassageKind.PROGRAM_MEMBERS,
        date=member_list_date(program, members),
        text=member_list_text(program, members, read.asker.project_id),
        member=None,
    )
    if program.concept_member is None:
        return ProgramSources(concept=None, members=members_file)
    concept = _read_concept(program, program.concept_member, read)
    if not isinstance(concept, SourceFile):
        return concept
    return ProgramSources(concept=concept, members=members_file)


def without_path(files: tuple[SourceFile, ...], path: str) -> tuple[SourceFile, ...]:
    """``files`` minus the one at ``path``, so the concept is kept once (182, D3)."""
    return tuple(file for file in files if file.path != path)


def _concept_path(program: Program) -> str:
    """The concept path; a program has one whenever it has a concept member."""
    if program.concept_path is None:
        raise ValueError(f"program {program.program_id!r} has no concept path")
    return program.concept_path


def _read_concept(
    program: Program, holder: str, read: ProgramRead
) -> SourceFile | SourcesProblem:
    if read.asker.project_id == holder:
        return _read_from_asker(program, holder, read)
    return _read_from_other_member(program, holder, read)


def _read_from_asker(
    program: Program, holder: str, read: ProgramRead
) -> SourceFile | SourcesProblem:
    """The asker holds the concept: read it at the commit its own reads pinned.

    No ``cf`` call. If the asker already read the file (it is also a rules or plan
    file) that one is relabelled and no git call is made.
    """
    path = _concept_path(program)
    for file in read.asker_reads.files:
        if file.path == path:
            relabelled = replace(file, kind=PassageKind.PROGRAM_CONCEPT, member=holder)
            return _within_limit(relabelled, holder, read.max_chars)
    git = GitReads(read.asker_reads.checkout, read.run, read.timeout_seconds)
    return _read_concept_file(git, read.asker_reads.commit, path, holder, read)


def _read_from_other_member(
    program: Program, holder: str, read: ProgramRead
) -> SourceFile | SourcesProblem:
    """The concept member's checkout, its target and pinned commit, then the file."""
    prefix = f"concept member {holder}"
    project = project_of(reference=holder, run=read.run)
    if isinstance(project, CFProjectNotFound):
        return SourcesProblem(
            SourcesProblemKind.MISSING,
            f"{prefix} is not a Context Forge project: {project.message}",
        )
    if isinstance(project, CfCallFailed):
        return unreadable(f"{prefix}: {project.detail}")
    checkout = Path(project.project_path)
    target = read_target(checkout, holder, read.run, read.timeout_seconds)
    if isinstance(target, ReadFailure):
        return unreadable(f"{prefix}: {target.detail}")
    git = GitReads(checkout, read.run, read.timeout_seconds)
    resolved = git.read(resolve_commit_args(target))
    if not isinstance(resolved, GitReadResult):
        return in_context(resolved, prefix)
    commit = resolved.stdout.strip()
    if not commit:
        return unreadable(f"{prefix}: target {target!r} resolved to no commit")
    return _read_concept_file(git, commit, _concept_path(program), holder, read)


def _read_concept_file(
    git: GitReads, commit: str, path: str, holder: str, read: ProgramRead
) -> SourceFile | SourcesProblem:
    """List the file's directory at ``commit``, then read its date and text."""
    prefix = f"concept member {holder}"
    parent, _, name = path.rpartition("/")
    names = Listings(git, commit).of(parent, prefix)
    if not isinstance(names, tuple):
        return names
    if name not in names:
        return SourcesProblem(
            SourcesProblemKind.MISSING, f"{prefix}: {path} is not in commit {commit}"
        )
    file = read_file(git, commit, SelectedFile(path, PassageKind.PROGRAM_CONCEPT))
    if not isinstance(file, SourceFile):
        return in_context(file, prefix)
    return _within_limit(replace(file, member=holder), holder, read.max_chars)


def _within_limit(
    file: SourceFile, holder: str, max_chars: int
) -> SourceFile | SourcesProblem:
    """The early size stop: raw concept text against what is still allowed."""
    if len(file.text) > max_chars:
        return SourcesProblem(
            SourcesProblemKind.TOO_LARGE,
            f"concept member {holder}: {file.path} is {len(file.text)} characters; "
            f"{max_chars} remain for program passages",
        )
    return file
