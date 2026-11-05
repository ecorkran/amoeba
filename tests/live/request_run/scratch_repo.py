"""The scratch provider repository of the live slice-writing tests (slice 180, D10).

A git repo on its default branch with a minimal initiative plan, one initiative with
one slice, and one small source file a "met" need can point to. It is registered as
a Context Forge project in a throwaway registry, and everything ``cf init`` wrote is
committed with the fixture files, so the tree is clean when a run starts.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

#: The scratch repo's target branch. The throwaway registry sets no
#: ``git.integration_branch``, so this is the target; every git call and assertion
#: of the tier uses this one name.
TARGET_BRANCH: Final = "main"

#: The fixture's one existing initiative and its one slice.
EXISTING_INITIATIVE_INDEX: Final = 100
EXISTING_SLICE_NAME: Final = "Note Store"

#: The requests index every case uses; it does not collide with the fixture's.
REQUESTS_INDEX: Final = 200

TOOL_TIMEOUT_SECONDS: Final = 60
PROJECT_NAME: Final = "scratch-provider"
#: Setup commits only; the pipeline's own commit uses whatever identity is configured.
_SETUP_IDENTITY: Final = (
    "-c",
    "user.name=Live Fixture",
    "-c",
    "user.email=fx@example.com",
)

INITIATIVE_PLAN_PATH: Final = (
    "project-documents/user/project-guides/001-initiative-plan.scratch.md"
)
SLICE_PLAN_PATH: Final = "project-documents/user/architecture/100-slices.notes.md"
SOURCE_PATH: Final = "src/notes.py"

_INITIATIVE_PLAN: Final = """\
---
docType: initiative-plan
layer: project
project: scratch-provider
dateCreated: 20261101
dateUpdated: 20261101
status: in_progress
---

# Initiative Plan: Scratch Provider

## Initiatives

1. [ ] **(100) Notes** — Store and list notes. Dependencies: None. Status: in_progress
"""

_SLICE_PLAN: Final = f"""\
---
docType: slice-plan
layer: project
project: scratch-provider
parent: user/project-guides/001-initiative-plan.scratch.md
archIndex: 100
component: notes
dateCreated: 20261101
dateUpdated: 20261101
status: in_progress
---

# Slice Plan: Notes

## Parent Document

`001-initiative-plan.scratch.md`

## Foundation Work

1. [ ] **(100) {EXISTING_SLICE_NAME}** — Keep notes in memory and read them back.
   **Value:** Notes exist.
   **Dependencies:** None
   **Risk Level:** Low
   **Relative Effort:** 1
"""

#: What a "met" need can point to: a function returning the number of notes.
_SOURCE: Final = '''\
"""A tiny notes library."""


def count_notes(notes: list[str]) -> int:
    """Return how many notes there are."""
    return len(notes)
'''

_FIXTURE_FILES: Final = {
    INITIATIVE_PLAN_PATH: _INITIATIVE_PLAN,
    SLICE_PLAN_PATH: _SLICE_PLAN,
    SOURCE_PATH: _SOURCE,
}


@dataclass(frozen=True)
class ScratchRepo:
    """A built provider repo: its path, the tool environment and its first commit."""

    path: Path
    environ: dict[str, str]
    fixture_commit: str


def run_tool(
    argv: list[str], directory: Path, environ: dict[str, str]
) -> subprocess.CompletedProcess[str]:
    """Run one ``git`` or ``cf`` call and fail loudly, with its output, on non-zero."""
    completed = subprocess.run(  # noqa: S603 - argv built by the tier, no shell
        argv,
        cwd=directory,
        env=environ,
        capture_output=True,
        text=True,
        timeout=TOOL_TIMEOUT_SECONDS,
        check=False,
    )
    if completed.returncode != 0:
        raise AssertionError(
            f"`{' '.join(argv)}` exited {completed.returncode}: "
            f"{completed.stdout}{completed.stderr}"
        )
    return completed


def git(repo: ScratchRepo, *args: str) -> str:
    """Stdout of a git call in the repo, trailing whitespace trimmed."""
    return run_tool(["git", *args], repo.path, repo.environ).stdout.strip()


def cf_json(repo: ScratchRepo, *args: str) -> Any:
    """Parsed JSON stdout of a ``cf`` call in the repo."""
    return json.loads(run_tool(["cf", *args], repo.path, repo.environ).stdout)


def build_scratch_repo(
    directory: Path, registry: Path, environ: dict[str, str]
) -> ScratchRepo:
    """Create the repo in the empty ``directory``, registered in ``registry``."""
    tool_environ = {**environ, "CONTEXT_FORGE_DATA_DIR": str(registry)}
    run_tool(["git", "init", "-q", "-b", TARGET_BRANCH], directory, tool_environ)
    run_tool(["cf", "init", "--lite", "--name", PROJECT_NAME], directory, tool_environ)
    for relative, text in _FIXTURE_FILES.items():
        path = directory / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    run_tool(["git", "add", "-A"], directory, tool_environ)
    run_tool(
        ["git", *_SETUP_IDENTITY, "commit", "-q", "-m", "chore: scratch fixture"],
        directory,
        tool_environ,
    )
    head = run_tool(["git", "rev-parse", "HEAD"], directory, tool_environ)
    repo = ScratchRepo(directory, tool_environ, head.stdout.strip())
    if git(repo, "status", "--porcelain"):
        raise AssertionError("the scratch repo is not clean after its fixture commit")
    return repo
