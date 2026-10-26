"""The one place the Runner starts ``git``: read-only and bounded (slice 128, D10).

``git_read`` checks the tick budget, runs under the call timeout with stdin closed and
prompts disabled, and refuses any subcommand outside :data:`GIT_SUBCOMMANDS`. The
Runner never merges, commits, checks out, resets, stashes, deletes a branch or pushes,
so the allowlist is two read commands. ``--no-optional-locks`` keeps even ``status``
from rewriting the index.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Final

from amoeba.runner.budget import TickBudget
from amoeba.runner.cf_call import CfCallFailed, CfRun, output_head, run_cf

GIT_EXECUTABLE: Final = "git"
SUBCOMMAND_STATUS: Final = "status"
SUBCOMMAND_MERGE_BASE: Final = "merge-base"

#: The only subcommands the Runner may run; anything else is a programming error.
GIT_SUBCOMMANDS: Final = frozenset({SUBCOMMAND_STATUS, SUBCOMMAND_MERGE_BASE})

#: Keeps git from waiting on credentials: with stdin closed it fails instead.
_ENV_NO_PROMPT: Final = {"GIT_TERMINAL_PROMPT": "0"}

_HEADER_PREFIX: Final = "# "
_HEADER_BRANCH_HEAD: Final = "branch.head"
_HEADER_BRANCH_OID: Final = "branch.oid"
_DETACHED: Final = "(detached)"
_NO_COMMIT_OID: Final = "(initial)"

# Porcelain v2 entry kinds, and how many space-separated fields precede the path.
_KIND_ORDINARY: Final = "1"
_KIND_RENAMED: Final = "2"
_KIND_UNMERGED: Final = "u"
_FIELDS_BEFORE_PATH: Final = {_KIND_ORDINARY: 8, _KIND_RENAMED: 9, _KIND_UNMERGED: 10}
_RENAME_SEPARATOR: Final = "\t"  # type-2 lines: new path, TAB, old path


@dataclass(frozen=True)
class GitReadResult:
    """``git`` ran to completion. The caller reads ``exit_code``."""

    exit_code: int
    stdout: str
    stderr_head: str


@dataclass(frozen=True)
class GitReadFailure:
    """``git`` timed out or could not run; ``detail`` names the command and why."""

    detail: str


@dataclass(frozen=True)
class GitStatus:
    """What ``git status --porcelain=v2 --branch`` says about a checkout."""

    #: The checked-out branch, or ``None`` when HEAD is detached.
    branch: str | None
    #: The head commit, or ``None`` before the first commit.
    head: str | None
    #: The path of every changed, staged, untracked or unmerged entry.
    dirty: tuple[str, ...]


def status_args() -> tuple[str, ...]:
    """The one ``status`` call: porcelain v2, branch header, untracked files shown."""
    return (
        "--no-optional-locks",
        SUBCOMMAND_STATUS,
        "--porcelain=v2",
        "--branch",
        "--untracked-files=normal",
    )


def is_ancestor_args(head: str, target: str) -> tuple[str, ...]:
    """``merge-base --is-ancestor``: exit 0 when ``head`` is in ``target``."""
    for value in (head, target):
        if value.startswith("-"):
            raise ValueError(f"not a commit or branch name: {value!r}")
    return (SUBCOMMAND_MERGE_BASE, "--is-ancestor", head, target)


def _subcommand(args: tuple[str, ...]) -> str:
    """The first argument that is not an option."""
    for arg in args:
        if not arg.startswith("-"):
            return arg
    raise ValueError("git arguments hold no subcommand")


def git_read(
    args: tuple[str, ...],
    cwd: Path,
    budget: TickBudget,
    run: CfRun,
    timeout_seconds: float,
) -> GitReadResult | GitReadFailure | None:
    """Run one allowlisted ``git`` command in ``cwd``.

    Returns:
        ``None`` when the tick budget refuses the call, a :class:`GitReadFailure` for a
        timeout or a missing executable, else the completed command.

    Raises:
        ValueError: ``args`` names a subcommand outside :data:`GIT_SUBCOMMANDS`.
    """
    subcommand = _subcommand(args)
    if subcommand not in GIT_SUBCOMMANDS:
        raise ValueError(f"git {subcommand} is not an allowed read")
    if not budget.allows_call():
        return None
    env = {**os.environ, **_ENV_NO_PROMPT}
    answer = run_cf(
        (GIT_EXECUTABLE, *args), partial(run, cwd=cwd, env=env), timeout_seconds
    )
    if isinstance(answer, CfCallFailed):
        return GitReadFailure(answer.detail)
    return _result(answer)


def _result(completed: subprocess.CompletedProcess[str]) -> GitReadResult:
    return GitReadResult(
        exit_code=completed.returncode,
        stdout=completed.stdout,
        stderr_head=output_head(completed),
    )


def _entry_path(line: str) -> str:
    """The path of one non-header status line, whatever its kind."""
    kind = line.split(" ", 1)[0]
    if kind == "?" or kind not in _FIELDS_BEFORE_PATH:
        # Untracked ("? <path>"), or an unknown kind: the rest of the line.
        return line.split(" ", 1)[1] if " " in line else line
    path = line.split(" ", _FIELDS_BEFORE_PATH[kind])[-1]
    return path.split(_RENAME_SEPARATOR, 1)[0] if kind == _KIND_RENAMED else path


def parse_porcelain_v2(text: str) -> GitStatus:
    """Parse ``status --porcelain=v2 --branch`` output.

    Header lines this parser does not know are ignored; every other non-empty line is
    a dirty entry, whose path is read by kind so a path with spaces survives. A rename
    reports its new path.
    """
    branch: str | None = None
    head: str | None = None
    dirty: list[str] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        if line.startswith(_HEADER_PREFIX):
            key, _, value = line[len(_HEADER_PREFIX) :].partition(" ")
            if key == _HEADER_BRANCH_HEAD:
                branch = None if value == _DETACHED else value
            elif key == _HEADER_BRANCH_OID:
                head = None if value == _NO_COMMIT_OID else value
            continue
        dirty.append(_entry_path(line))
    return GitStatus(branch=branch, head=head, dirty=tuple(dirty))
