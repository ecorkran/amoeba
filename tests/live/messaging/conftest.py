"""Fixtures for the messaging live test (slice 240, task 14.1).

Collected only when the tier is named (``uv run pytest tests/live/messaging``). It
reuses the pause tier's throwaway member, program and settings, so the three
``AMOEBA_LIVE_*`` variables are read at collection and a missing one fails by name. No
model runs.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from live.messaging.repos import Toolchain, build_toolchain
from live.pause.conftest import live_settings, pause_world
from live.pause.harness import PauseWorld

__all__ = ["live_settings", "pause_world", "toolchain"]


@pytest.fixture
def toolchain(tmp_path: Path, pause_world: PauseWorld) -> Iterator[Toolchain]:
    """Three real repos in one program and one throwaway store."""
    yield build_toolchain(tmp_path, pause_world)
