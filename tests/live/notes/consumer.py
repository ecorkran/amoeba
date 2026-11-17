"""Two consumers of the pause tier's member, one of each ``consumed`` mode (slice 243,
8.1).

Modelled on ``live.program.consumer``: each consumer is a committed git repo and a
Context Forge project in the provider's data directory, a member of its program and
store, and depends on the provider. The shared harness is not edited.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from amoeba.cli.exit_codes import EXIT_OK
from live.messaging.repos import build_repo
from live.pause.harness import CF_PROJECT_NAME, PROGRAM_ID, PauseWorld, run_amoeba

SOURCE_NAME = "notes-src"
RELEASE_NAME = "notes-rel"


@dataclass(frozen=True)
class NotesProgram:
    """The provider and its two consumers: each a world whose ``repo`` is its
    checkout."""

    provider: PauseWorld
    from_source: PauseWorld
    from_release: PauseWorld


def _consumer(parent: Path, provider: PauseWorld, name: str, mode: str) -> PauseWorld:
    world = build_repo(parent, provider, name)
    added = run_amoeba(
        world,
        "add",
        "--program",
        PROGRAM_ID,
        "--project",
        name,
        "--depends-on",
        f"{CF_PROJECT_NAME}:{mode}",
    )
    assert added.returncode == EXIT_OK, added.stderr + added.stdout
    return world


def build_notes_program(parent: Path, provider: PauseWorld) -> NotesProgram:
    return NotesProgram(
        provider=provider,
        from_source=_consumer(parent, provider, SOURCE_NAME, "from_source"),
        from_release=_consumer(parent, provider, RELEASE_NAME, "from_release"),
    )
