"""The client part: what a call reads from its own directory (slice 261, D5).

This runs on the calling machine, before any store work: ``cf get`` for the
directory's Context Forge project and, for ``add``, ``git remote get-url origin``
reduced to the form that leaves the machine. Nothing here touches the store. Not being
a project is a gathered value, not an error; a ``cf`` or ``git`` failure raises
``ContextForgeError``, before any hub call.

The address git prints can hold a password. It is reduced inside this module and the
raw text, git's stdout and git's stderr reach no exception and no log line.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

from amoeba.operations.errors import ContextForgeError
from amoeba.operations.here_document import (
    HereCaller,
    HereCheckout,
    HereNotAProject,
)
from amoeba.operations.origin import reduce_origin
from amoeba.upstream.context_forge.cli_call import CfCallFailed, CfRun
from amoeba.upstream.context_forge.project_of import (
    CFProject,
    CFProjectNotFound,
    project_of,
)
from amoeba.upstream.git_read import (
    GIT_EXECUTABLE,
    GitReadFailure,
    git_read,
    remote_origin_args,
)

#: Each ``git`` call waits at most this long (D4, D5).
ORIGIN_READ_TIMEOUT_SECONDS: Final = 10.0

#: ``git remote get-url origin`` exits 2 with "No such remote" when there is none.
NO_SUCH_REMOTE_EXIT_CODE: Final = 2
GIT_ENTRY: Final = ".git"


def _project_in(directory: Path, run: CfRun) -> CFProject | HereNotAProject:
    """The directory's project, or why it has none.

    Raises:
        ContextForgeError: ``cf`` failed to give a usable answer.
    """
    project = project_of(directory=directory, run=run)
    if isinstance(project, CfCallFailed):
        raise ContextForgeError(project.detail)
    if isinstance(project, CFProjectNotFound):
        return HereNotAProject(not_a_project=project.message)
    return project


def gather_caller(directory: Path, run: CfRun) -> HereCaller | HereNotAProject:
    """The caller's Context Forge project id; one ``cf`` call.

    Raises:
        ContextForgeError: ``cf`` failed to give a usable answer.
    """
    project = _project_in(directory, run)
    if isinstance(project, HereNotAProject):
        return project
    return HereCaller(project_id=project.id)


def git_root(path: Path) -> Path | None:
    """The nearest of ``path`` (resolved) and its parents with a ``.git`` entry.

    A directory for an ordinary clone, a file for a linked worktree. ``None`` when
    there is none, which is decided before git runs and not from git's exit code.
    """
    resolved = path.resolve()
    for candidate in (resolved, *resolved.parents):
        if (candidate / GIT_ENTRY).exists():
            return candidate
    return None


def _origin_of(path: Path, git: CfRun) -> str | None:
    """The reduced ``origin`` of the repo at ``path``, or ``None`` for no remote.

    Raises:
        ContextForgeError: ``git`` failed in any way but "no such remote". The text
            is the command and why, never git's output.
    """
    if git_root(path) is None:
        return None
    answer = git_read(remote_origin_args(), path, git, ORIGIN_READ_TIMEOUT_SECONDS)
    if isinstance(answer, GitReadFailure):
        raise ContextForgeError(answer.detail)
    if answer.exit_code == NO_SUCH_REMOTE_EXIT_CODE:
        return None
    if answer.exit_code != 0:
        command = " ".join((GIT_EXECUTABLE, *remote_origin_args()))
        raise ContextForgeError(f"`{command}` exited {answer.exit_code}")
    return reduce_origin(answer.stdout)


def gather_checkout(
    directory: Path, run: CfRun, git: CfRun
) -> HereCheckout | HereNotAProject:
    """The project's id, name and path, and the repo's reduced ``origin``.

    One ``cf`` call, then one ``git`` call when the project's path is in a repo.

    Raises:
        ContextForgeError: ``cf`` or ``git`` failed to give a usable answer.
    """
    project = _project_in(directory, run)
    if isinstance(project, HereNotAProject):
        return project
    return HereCheckout(
        project_id=project.id,
        name=project.name,
        path=project.project_path,
        origin=_origin_of(Path(project.project_path), git),
    )
