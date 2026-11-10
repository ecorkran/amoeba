"""Read the rules and plan files at one committed commit of the target (slice 143).

Every git call this slice makes is here, and so is the only knowledge of where Context
Forge keeps its documents (D1). Reads go through ``git show`` and ``git log`` at a
commit resolved once (D2), so an uncommitted edit, an untracked file and a merge that
lands mid-read are all invisible. Absence is decided from directory listings only: a
non-zero exit from git is always :data:`SourcesProblemKind.UNREADABLE`, never "absent".

A result is a value or a :class:`SourcesProblem`; nothing here retries or raises for
what the repository can cause.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final

from amoeba.answering.passages import (
    PassageKind,
    PlanRow,
    SourceFile,
    SourcesProblem,
    SourcesProblemKind,
    match_rules_entry,
    parse_git_date,
    select_plan_files,
    unreadable,
)
from amoeba.upstream.context_forge.cli_call import CfRun
from amoeba.upstream.git_read import (
    GitReadFailure,
    GitReadResult,
    git_read,
    last_change_args,
    parse_tree_directories,
    parse_tree_listing,
    resolve_commit_args,
    show_object_args,
)

#: Where Context Forge keeps a project's documents, observed on CF (process contract,
#: "Context Forge shapes"). Nothing else in Amoeba spells a directory or a file name.
USER_ROOT: Final = "project-documents/user"
_PROJECT_GUIDES: Final = f"{USER_ROOT}/project-guides"
_ARCHITECTURE: Final = f"{USER_ROOT}/architecture"

#: Plan files in the order they are offered. Only the slice plan is required: a slice
#: exists in CF only through one, while design and tasks come in later phases.
PLAN_ROWS: Final = (
    PlanRow(_PROJECT_GUIDES, "000-concept.*.md", required=False),
    PlanRow(_PROJECT_GUIDES, "001-initiative-plan.*.md", required=False),
    PlanRow(_ARCHITECTURE, "{initiative}-arch.*.md", required=False),
    PlanRow(_ARCHITECTURE, "{initiative}-slices.*.md", required=True),
    PlanRow(f"{USER_ROOT}/slices", "{slice}-slice.*.md", required=False),
    PlanRow(f"{USER_ROOT}/tasks", "{slice}-tasks.*.md", required=False),
)


@dataclass(frozen=True)
class SliceRef:
    """A slice and its initiative, as CF indexes them."""

    slice_index: int
    initiative_index: int


@dataclass(frozen=True)
class SelectedFile:
    path: str
    kind: PassageKind


@dataclass(frozen=True)
class SourceSelection:
    """The files to read, in offer order, and the commit they are read at."""

    commit: str
    files: tuple[SelectedFile, ...]


@dataclass(frozen=True)
class CommittedSources:
    commit: str
    files: tuple[SourceFile, ...]


@dataclass(frozen=True)
class GitReads:
    """The arguments every git call here shares."""

    repo: Path
    run: CfRun
    timeout_seconds: float

    def read(self, args: tuple[str, ...]) -> GitReadResult | SourcesProblem:
        """One read: the result, or ``sources_unreadable`` for any failure."""
        answer = git_read(args, self.repo, self.run, self.timeout_seconds)
        shown = "git " + " ".join(args)
        if isinstance(answer, GitReadFailure):
            return unreadable(answer.detail)
        if answer.exit_code != 0:
            return unreadable(
                f"`{shown}` exited {answer.exit_code}: {answer.stderr_head}"
            )
        return answer


def _parent_and_name(entry: str) -> tuple[str, str]:
    parent, _, name = entry.rpartition("/")
    return parent, name


def _user_subdirectory(directory: str) -> str:
    """``directory`` relative to :data:`USER_ROOT`; it must sit directly under it."""
    relative = directory.removeprefix(f"{USER_ROOT}/")
    if relative == directory or "/" in relative:
        raise ValueError(f"{directory!r} is not directly under {USER_ROOT}")
    return relative


class Listings:
    """Directory listings at the pinned commit, each read once."""

    def __init__(self, git: GitReads, commit: str) -> None:
        self._git = git
        self._commit = commit
        self._by_directory: dict[str, tuple[str, ...]] = {}

    def of(self, directory: str, context: str) -> tuple[str, ...] | SourcesProblem:
        """File names in ``directory``; ``context`` prefixes a failure's detail."""
        if directory in self._by_directory:
            return self._by_directory[directory]
        answer = self._git.read(show_object_args(self._commit, directory))
        if not isinstance(answer, GitReadResult):
            return in_context(answer, context)
        names = parse_tree_listing(answer.stdout)
        self._by_directory[directory] = names
        return names


def in_context(problem: SourcesProblem, context: str) -> SourcesProblem:
    return SourcesProblem(problem.kind, f"{context}: {problem.detail}")


def locate_sources(
    repo: Path,
    target: str,
    slice_ref: SliceRef | None,
    rules_paths: tuple[str, ...],
    run: CfRun,
    timeout_seconds: float,
) -> SourceSelection | SourcesProblem:
    """Resolve ``target`` to a commit and pick the files to read, rules then plan.

    With ``slice_ref`` ``None`` (a run with no slice) no plan file is selected.

    A file picked twice is kept at its first position. Makes ``2 + L`` git calls for
    ``L`` directory listings; reading the files is :func:`read_committed_sources`.
    """
    git = GitReads(repo, run, timeout_seconds)
    resolved = git.read(resolve_commit_args(target))
    if not isinstance(resolved, GitReadResult):
        return resolved
    commit = resolved.stdout.strip()
    if not commit:
        return unreadable(f"target {target!r} resolved to no commit")
    listings = Listings(git, commit)
    rules = _select_rules(listings, rules_paths)
    if not isinstance(rules, tuple):
        return rules
    plan = () if slice_ref is None else _select_plan(git, listings, commit, slice_ref)
    if not isinstance(plan, tuple):
        return plan
    chosen: dict[str, SelectedFile] = {}
    for selected in (*rules, *plan):
        chosen.setdefault(selected.path, selected)  # first position, first kind
    return SourceSelection(commit, tuple(chosen.values()))


def _select_rules(
    listings: Listings, rules_paths: tuple[str, ...]
) -> tuple[SelectedFile, ...] | SourcesProblem:
    chosen: list[SelectedFile] = []
    for entry in rules_paths:
        parent, _ = _parent_and_name(entry)
        names = listings.of(parent, f"rules entry {entry!r}")
        if not isinstance(names, tuple):
            return names
        matched = match_rules_entry(entry, names)
        if not matched:
            return SourcesProblem(
                SourcesProblemKind.MISSING, f"rules entry {entry!r} matches no file"
            )
        prefix = f"{parent}/" if parent else ""
        chosen.extend(SelectedFile(prefix + n, PassageKind.RULE) for n in matched)
    return tuple(chosen)


def _select_plan(
    git: GitReads, listings: Listings, commit: str, slice_ref: SliceRef
) -> tuple[SelectedFile, ...] | SourcesProblem:
    root = git.read(show_object_args(commit, USER_ROOT))
    if not isinstance(root, GitReadResult):
        return in_context(root, USER_ROOT)
    present = set(parse_tree_directories(root.stdout))
    found: dict[str, tuple[str, ...]] = {}
    for directory in dict.fromkeys(row.directory for row in PLAN_ROWS):
        if _user_subdirectory(directory) not in present:
            continue
        names = listings.of(directory, f"plan directory {directory}")
        if not isinstance(names, tuple):
            return names
        found[directory] = names
    indexes = (slice_ref.slice_index, slice_ref.initiative_index)
    required = [row for row in PLAN_ROWS if row.required]
    if not select_plan_files(required, found, *indexes):
        return SourcesProblem(
            SourcesProblemKind.MISSING,
            f"no slice plan for initiative {slice_ref.initiative_index}",
        )
    paths = select_plan_files(PLAN_ROWS, found, *indexes)
    return tuple(SelectedFile(path, PassageKind.PLAN) for path in paths)


def read_committed_sources(
    repo: Path,
    target: str,
    slice_ref: SliceRef | None,
    rules_paths: tuple[str, ...],
    max_chars: int,
    run: CfRun,
    timeout_seconds: float,
) -> CommittedSources | SourcesProblem:
    """Locate the files, then read each one's date and text at the pinned commit.

    Stops with ``sources_too_large`` as soon as the text read exceeds ``max_chars``,
    which bounds the git calls to the size limit rather than to what a glob matches.
    A date that cannot be read is ``sources_unreadable``; there is no fallback date.
    """
    selection = locate_sources(
        repo, target, slice_ref, rules_paths, run, timeout_seconds
    )
    if not isinstance(selection, SourceSelection):
        return selection
    git = GitReads(repo, run, timeout_seconds)
    files: list[SourceFile] = []
    total = 0
    for chosen in selection.files:
        read = read_file(git, selection.commit, chosen)
        if not isinstance(read, SourceFile):
            return read
        total += len(read.text)
        if total > max_chars:
            return SourcesProblem(
                SourcesProblemKind.TOO_LARGE,
                f"rules and plan text is at least {total} characters; "
                f"the limit is {max_chars}",
            )
        files.append(read)
    return CommittedSources(selection.commit, tuple(files))


def read_file(
    git: GitReads, commit: str, chosen: SelectedFile
) -> SourceFile | SourcesProblem:
    dated = git.read(last_change_args(commit, chosen.path))
    if not isinstance(dated, GitReadResult):
        return in_context(dated, chosen.path)
    date = parse_git_date(dated.stdout)
    if date is None:
        return unreadable(f"no usable commit date for {chosen.path}: {dated.stdout!r}")
    try:
        shown = git.read(show_object_args(commit, chosen.path))
    except UnicodeDecodeError:
        # A binary file: run_cf decodes git's output as text. Reported by path, not
        # raised, because the repository (not a bug here) caused it.
        return unreadable(f"{chosen.path} is not UTF-8 text")
    if not isinstance(shown, GitReadResult):
        return in_context(shown, chosen.path)
    return SourceFile(chosen.path, chosen.kind, date, shown.stdout, member=None)
