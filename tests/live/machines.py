"""A client machine of the two-machine fixture with real ``cf`` and ``git`` (261, 262).

Each machine has its own ``CONTEXT_FORGE_DATA_DIR``, so the same kind of repo is a
different Context Forge project on each, and its environment replaces the fixture's
stubs (``FixtureHub.home_environment``). This build's ``amoeba`` is first on ``PATH``,
so a child the machine starts, and a woken agent's own ``amoeba`` calls, reach the same
build. ``extra`` adds or replaces variables, such as a real ``HOME`` and provider
credentials for a machine that runs ``sq`` with models.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Final

from git_repo import git
from hub_fixture import ClientHome, FixtureHub
from live_environment import process_environment

CF_TIMEOUT_SECONDS: Final = 120


class Machine:
    """One client machine: its home, its own Context Forge data directory, its repos."""

    def __init__(
        self,
        hub: FixtureHub,
        client: ClientHome,
        extra: Mapping[str, str] | None = None,
    ) -> None:
        self.hub = hub
        self.client = client
        self.data_dir = client.home / "cf-data"
        self.data_dir.mkdir()
        path = os.pathsep.join([str(Path(sys.executable).parent), os.environ["PATH"]])
        self.environment = {
            "PATH": path,
            "CONTEXT_FORGE_DATA_DIR": str(self.data_dir),
            **(extra or {}),
        }
        hub.home_environment[client.home] = self.environment

    @property
    def environ(self) -> dict[str, str]:
        """The whole environment this machine's ``amoeba`` calls get."""
        return self.hub.env_for(self.client.home)

    def repo(self, name: str, files: Mapping[str, str] | None = None) -> Path:
        """A committed git repo that is a Context Forge project on this machine."""
        repo = self.client.home / "repos" / name
        repo.mkdir(parents=True)
        git(repo, "init", "-q", "-b", "main")
        for relative, text in {"README.md": f"{name}\n", **(files or {})}.items():
            (repo / relative).write_text(text, encoding="utf-8")
        git(repo, "add", "-A")
        git(repo, "commit", "-q", "-m", "seed")
        subprocess.run(
            ["cf", "init", "--lite", "--name", name],
            cwd=repo,
            env=process_environment(os.environ, **self.environment),
            capture_output=True,
            text=True,
            timeout=CF_TIMEOUT_SECONDS,
            check=True,
        )
        git(repo, "add", "-A")
        if git(repo, "status", "--porcelain").stdout.strip():
            git(repo, "commit", "-q", "-m", "cf init")
        return repo.resolve()

    def run(self, repo: Path, *args: str, expect: int = 0) -> dict[str, Any]:
        """``amoeba <args> -j`` in ``repo``; the document, after checking the exit."""
        done = self.client.run_in(repo, *args, "-j")
        assert done.code == expect, (
            f"amoeba {' '.join(args)} on {self.client.name} exited {done.code}\n"
            f"{done.out}\n{done.err}"
        )
        document: dict[str, Any] = json.loads(done.out)
        return document
