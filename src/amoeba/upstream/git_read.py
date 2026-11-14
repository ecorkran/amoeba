"""The one place Amoeba starts ``git``: read-only and bounded.

``git_read`` runs under the call timeout with stdin closed and prompts disabled, and
refuses any subcommand outside :data:`GIT_SUBCOMMANDS`. Amoeba never merges, commits,
checks out, resets, stashes, deletes a branch or pushes, so the allowlist is three read
commands: ``show``, ``log`` and ``ls-tree`` for objects at a pinned commit (never the
working tree).
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Final

from amoeba.upstream.context_forge.cli_call import (
    CfCallFailed,
    CfRun,
    output_head,
    run_cf,
)

GIT_EXECUTABLE: Final = "git"
SUBCOMMAND_SHOW: Final = "show"
SUBCOMMAND_LOG: Final = "log"
SUBCOMMAND_LS_TREE: Final = "ls-tree"

#: The only subcommands Amoeba may run; anything else is a programming error.
GIT_SUBCOMMANDS: Final = frozenset(
    {SUBCOMMAND_SHOW, SUBCOMMAND_LOG, SUBCOMMAND_LS_TREE}
)

#: Keeps git from waiting on credentials: with stdin closed it fails instead.
_ENV_NO_PROMPT: Final = {"GIT_TERMINAL_PROMPT": "0"}


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


def _refuse_option(*values: str) -> None:
    """Raise when a commit or branch name could be read by git as an option."""
    for value in values:
        if value.startswith("-"):
            raise ValueError(f"not a commit or branch name: {value!r}")


def resolve_commit_args(target: str) -> tuple[str, ...]:
    """``log -1 --format=%H``: the commit a branch name points at."""
    _refuse_option(target)
    return (SUBCOMMAND_LOG, "-1", "--format=%H", target)


def show_object_args(commit: str, path: str) -> tuple[str, ...]:
    """``show <commit>:<path>``: a blob's content, or a tree's entries.

    An empty ``path`` names the root tree. A path cannot be read as an option here,
    because it follows the colon.
    """
    _refuse_option(commit)
    return (SUBCOMMAND_SHOW, f"{commit}:{path}")


def ls_tree_args(commit: str, directory: str) -> tuple[str, ...]:
    """``ls-tree --name-only <commit> -- <directory>/``: the entries of a directory.

    Exit 0 with empty output means the directory is absent at the commit; a
    directory that is absent is not an error for ``ls-tree``, unlike ``show``.
    """
    _refuse_option(commit)
    # ``--`` ends the options, so a directory named ``-x`` is a path, not a flag.
    return (SUBCOMMAND_LS_TREE, "--name-only", commit, "--", f"{directory}/")


def last_change_args(commit: str, path: str) -> tuple[str, ...]:
    """``log -1 --format=%cI``: committer date of the last commit on ``path``."""
    _refuse_option(commit)
    return (SUBCOMMAND_LOG, "-1", "--format=%cI", commit, "--", path)


def _subcommand(args: tuple[str, ...]) -> str:
    """The first argument that is not an option."""
    for arg in args:
        if not arg.startswith("-"):
            return arg
    raise ValueError("git arguments hold no subcommand")


def git_read(
    args: tuple[str, ...],
    cwd: Path,
    run: CfRun,
    timeout_seconds: float,
) -> GitReadResult | GitReadFailure:
    """Run one allowlisted ``git`` command in ``cwd``.

    Returns:
        A :class:`GitReadFailure` for a timeout or a missing executable, else the
        completed command.

    Raises:
        ValueError: ``args`` names a subcommand outside :data:`GIT_SUBCOMMANDS`.
    """
    subcommand = _subcommand(args)
    if subcommand not in GIT_SUBCOMMANDS:
        raise ValueError(f"git {subcommand} is not an allowed read")
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


_TREE_HEADER_PREFIX: Final = "tree "
_DIRECTORY_SUFFIX: Final = "/"


def _tree_entries(text: str) -> tuple[str, ...]:
    """The entry lines of ``git show <commit>:<dir>`` output, without the header.

    Only the first non-blank line can be the ``tree …`` header, so a file whose name
    starts with ``tree `` is still listed.
    """
    entries: list[str] = []
    first = True
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if not (first and line.startswith(_TREE_HEADER_PREFIX)):
            entries.append(line)
        first = False
    return tuple(entries)


def parse_tree_listing(text: str) -> tuple[str, ...]:
    """The file names in ``git show <commit>:<dir>`` output, in git's order.

    Skips the ``tree …`` header and blank lines and drops subdirectories (names ending
    in ``/``); directories are not walked. Trailing whitespace and CRLF are tolerated.
    """
    return tuple(e for e in _tree_entries(text) if not e.endswith(_DIRECTORY_SUFFIX))


def parse_tree_directories(text: str) -> tuple[str, ...]:
    """The subdirectory names in the same output, without their trailing ``/``."""
    return tuple(
        e.removesuffix(_DIRECTORY_SUFFIX)
        for e in _tree_entries(text)
        if e.endswith(_DIRECTORY_SUFFIX)
    )
