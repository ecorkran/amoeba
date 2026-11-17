"""Fixtures for the notes live test (slice 243, 8.1).

Collected only when the tier is named (``uv run pytest tests/live/notes``). It reuses
the pause tier's throwaway provider and settings, so the three ``AMOEBA_LIVE_*``
variables are read at collection and a missing one fails by name. No model runs.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from live.notes.consumer import NotesProgram, build_notes_program
from live.pause.conftest import live_settings, pause_world
from live.pause.harness import PauseWorld

__all__ = ["live_settings", "notes_program", "pause_world"]


@pytest.fixture
def notes_program(tmp_path: Path, pause_world: PauseWorld) -> Iterator[NotesProgram]:
    """The provider and a consumer of each mode, in one program and one store."""
    yield build_notes_program(tmp_path, pause_world)
