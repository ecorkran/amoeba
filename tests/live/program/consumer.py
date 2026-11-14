"""A second member of the pause tier's program, one that depends on the provider
(slice 227, 6.2).

The shared harness is not edited: the consumer reuses the provider world's environment,
so both members share one ``cf-data`` directory (one ``cf list projects`` shows both)
and one ``AMOEBA_HOME`` and config (one program in one store).
"""

from __future__ import annotations

import dataclasses
import subprocess
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

CONSUMER_PROJECT_NAME: Final = "amoeba-live-consumer"


def build_consumer(parent: Path, provider: PauseWorld) -> PauseWorld:
    """A committed git repo, a Context Forge project in the provider's data directory,
    and a program member that depends on the provider."""
    repo = parent / "consumer"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    (repo / "README.md").write_text("consumer\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "seed")
    subprocess.run(
        ["cf", "init", "--lite", "--name", CONSUMER_PROJECT_NAME],
        cwd=repo,
        env=provider.environ,
        capture_output=True,
        text=True,
        timeout=CF_TIMEOUT_SECONDS,
        check=True,
    )
    git(repo, "add", "-A")
    if git(repo, "status", "--porcelain").stdout.strip():
        git(repo, "commit", "-q", "-m", "cf init")
    consumer = dataclasses.replace(provider, repo=repo)
    added = run_amoeba(
        consumer,
        "add",
        "--program",
        PROGRAM_ID,
        "--project",
        CONSUMER_PROJECT_NAME,
        "--depends-on",
        CF_PROJECT_NAME,
    )
    assert added.returncode == 0, added.stderr + added.stdout
    return consumer
