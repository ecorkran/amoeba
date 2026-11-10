"""Real temporary git repositories for the slice 128 git-read tests.

Every call runs real ``git`` with the identity set by ``-c`` flags, so nothing reads
or writes the developer's global config.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from live_environment import process_environment

IDENTITY = ("-c", "user.name=Amoeba Test", "-c", "user.email=test@example.invalid")


def git(
    repo: Path,
    *args: str,
    check: bool = True,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run ``git`` in ``repo``; a non-zero exit raises unless ``check`` is False.

    ``env`` adds variables to the named process variables for this call only.
    """
    return subprocess.run(
        ["git", *IDENTITY, *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=check,
        env=process_environment(os.environ, **env) if env else None,
    )


def commit_file(
    repo: Path, name: str, text: str, message: str, *, date: str | None = None
) -> str:
    """Write ``name``, commit it, and return the new head.

    ``date`` (ISO 8601) fixes both the author and the committer date of the commit.
    """
    path = repo / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    git(repo, "add", "-f", "--", name)  # -f: a rig checkout ignores everything
    dated = {"GIT_COMMITTER_DATE": date, "GIT_AUTHOR_DATE": date} if date else None
    git(repo, "commit", "-q", "-m", message, env=dated)
    return head_of(repo)


def head_of(repo: Path) -> str:
    return git(repo, "rev-parse", "HEAD").stdout.strip()


def make_repo(path: Path, branch: str = "main") -> Path:
    """Create a repository on ``branch`` with one commit."""
    path.mkdir(parents=True, exist_ok=True)
    git(path, "init", "-q", "-b", branch)
    commit_file(path, "README.md", "seed\n", "seed")
    return path


def make_branch(repo: Path, name: str) -> None:
    """Create ``name`` at HEAD and switch to it."""
    git(repo, "checkout", "-q", "-b", name)


def switch(repo: Path, name: str) -> None:
    git(repo, "checkout", "-q", name)


def merge_branch(repo: Path, branch: str, *, conflict_ok: bool = False) -> None:
    """Merge ``branch`` into the current branch with a merge commit."""
    result = git(
        repo, "merge", "--no-ff", "-q", "-m", f"merge {branch}", branch, check=False
    )
    if result.returncode != 0 and not conflict_ok:
        raise RuntimeError(f"git merge {branch} failed: {result.stderr}")


def delete_branch(repo: Path, name: str) -> None:
    git(repo, "branch", "-D", name)


def detach_head(repo: Path) -> None:
    git(repo, "checkout", "-q", "--detach")
