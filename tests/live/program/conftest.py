"""Fixtures for the program-dependencies live test (slice 227, 6.2).

Collected only when the tier is named (``uv run pytest tests/live/program``). It reuses
the pause tier's throwaway provider and settings, so the three ``AMOEBA_LIVE_*``
variables are read at collection and a missing one fails by name. No model runs.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from live.pause.conftest import live_settings, pause_world
from live.pause.harness import PauseWorld
from live.program.consumer import build_consumer

__all__ = ["live_settings", "pause_world", "program_worlds"]


@pytest.fixture
def program_worlds(
    tmp_path: Path, pause_world: PauseWorld
) -> Iterator[tuple[PauseWorld, PauseWorld]]:
    """The provider world and a consumer of it, in one program and one store."""
    yield pause_world, build_consumer(tmp_path, pause_world)
