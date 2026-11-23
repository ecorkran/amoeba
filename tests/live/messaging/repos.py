"""Three members of one program, for the messaging live test (slice 240, 14.1).

The pause tier's member plays the squadron repo; ``cf-s`` and ``guide-s`` are two more
committed git repos, each a Context Forge project in the same throwaway data directory
(one ``cf`` sees all three) and a member of the same program and store. The shared
harness is not edited: each repo reuses the first world's environment, which names the
throwaway ``AMOEBA_HOME`` and ``CONTEXT_FORGE_DATA_DIR``.
"""

from __future__ import annotations

import dataclasses
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from git_repo import git

from live.pause.harness import (
    CF_PROJECT_NAME,
    CF_TIMEOUT_SECONDS,
    PROGRAM_ID,
    PauseWorld,
    run_amoeba,
)

#: The Context Forge names the requests are addressed to.
SQUADRON_NAME: Final = CF_PROJECT_NAME
FORGE_NAME: Final = "cf-s"
GUIDE_NAME: Final = "guide-s"


@dataclass(frozen=True)
class Toolchain:
    """The three members: each a world whose ``repo`` is its checkout."""

    squadron: PauseWorld
    forge: PauseWorld
    guide: PauseWorld


def build_repo(parent: Path, base: PauseWorld, name: str) -> PauseWorld:
    """A committed git repo, a Context Forge project in ``base``'s data directory, and
    a member of ``base``'s program."""
    repo = parent / name
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    (repo / "README.md").write_text(f"{name}\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "seed")
    subprocess.run(
        ["cf", "init", "--lite", "--name", name],
        cwd=repo,
        env=base.environ,
        capture_output=True,
        text=True,
        timeout=CF_TIMEOUT_SECONDS,
        check=True,
    )
    git(repo, "add", "-A")
    if git(repo, "status", "--porcelain").stdout.strip():
        git(repo, "commit", "-q", "-m", "cf init")
    world = dataclasses.replace(base, repo=repo)
    added = run_amoeba(world, "add", "--program", PROGRAM_ID)
    assert added.returncode == 0, added.stderr + added.stdout
    return world


def build_toolchain(parent: Path, squadron: PauseWorld) -> Toolchain:
    return Toolchain(
        squadron=squadron,
        forge=build_repo(parent, squadron, FORGE_NAME),
        guide=build_repo(parent, squadron, GUIDE_NAME),
    )
