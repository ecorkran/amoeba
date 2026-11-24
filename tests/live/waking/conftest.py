"""Fixtures for the waking live test (slice 244, 9.2).

Collected only when the tier is named (``uv run pytest tests/live/waking``). It reuses
the pause tier's throwaway member and settings, so the three ``AMOEBA_LIVE_*``
variables are read at collection and a missing one fails by name. No model runs and
nothing is spent: the woken command is a fixture script.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from hub_fixture import two_machine_hub

from live.pause.conftest import live_settings, pause_world
from live.pause.harness import PauseWorld
from live.waking.split import SplitWaking, build_split_waking
from live.waking.split import reaping as reaping_split
from live.waking.world import WakingWorld, build_waking_world, reaping

__all__ = ["live_settings", "pause_world", "split_waking", "waking"]


@pytest.fixture
def waking(tmp_path: Path, pause_world: PauseWorld) -> Iterator[WakingWorld]:
    """A sender and a woken member in one program and one throwaway store; whatever a
    case leaves running is stopped afterwards."""
    with reaping(build_waking_world(tmp_path, pause_world)) as world:
        yield world


@pytest.fixture
def split_waking(tmp_path: Path) -> Iterator[SplitWaking]:
    """The sender on ``alpha`` and the woken member on ``beta``, behind a real hub;
    whatever a case leaves running is stopped afterwards."""
    with (
        two_machine_hub(tmp_path) as hub,
        reaping_split(build_split_waking(hub)) as split,
    ):
        yield split
