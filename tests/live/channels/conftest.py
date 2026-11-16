"""Fixtures for the channels live tier (slice 241, D10, 11.1).

Collected only when the tier is named (``uv run pytest tests/live/channels``). The
session model, ``AMOEBA_LIVE_CHANNEL_MODEL``, is read at collection, and the pause
tier's three ``AMOEBA_LIVE_*`` variables with its world; a missing one fails the tier
by name.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from live_settings import read_channel_model

from live.channels.world import ChannelWorld, build_channel_world
from live.pause.conftest import live_settings, pause_world
from live.pause.harness import PauseWorld

__all__ = ["channel_model", "channel_world", "live_settings", "pause_world"]

_CHANNEL_MODEL = read_channel_model(os.environ)


@pytest.fixture(scope="session")
def channel_model() -> str:
    return _CHANNEL_MODEL


@pytest.fixture
def channel_world(
    tmp_path: Path, pause_world: PauseWorld, channel_model: str
) -> Iterator[ChannelWorld]:
    """``cf-s`` and ``sq-s`` in one program, and ``outside``, under a throwaway home."""
    yield build_channel_world(tmp_path, pause_world, channel_model)
