"""Fixtures for the hold live tests (slice 242, task 8.1).

Collected only when the tier is named (``uv run pytest tests/live/hold``). It reuses
the pause tier's throwaway member, program and settings, so the three
``AMOEBA_LIVE_*`` variables are read at collection and a missing one fails by name;
nothing is skipped and nothing has a default.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from live.hold.harness import HoldWorld, build_hold_world
from live.pause.conftest import live_settings, pause_world
from live.pause.harness import PauseWorld

__all__ = ["hold_world", "live_settings", "pause_world"]


@pytest.fixture
def hold_world(tmp_path: Path, pause_world: PauseWorld) -> Iterator[HoldWorld]:
    """``sq-s`` and ``cf-s`` in one program and one throwaway store."""
    yield build_hold_world(tmp_path, pause_world)
