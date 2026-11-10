"""Fixtures for the pause live tests (slice 223, D15).

Collected only when the tier is named (``uv run pytest tests/live``). The three
``AMOEBA_LIVE_*`` variables are read at collection and a missing one fails the tier
by name; nothing is skipped and nothing has a default.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from live_settings import LiveSettings, read_live_settings

from live.pause.harness import PauseWorld, build_world

_SETTINGS = read_live_settings(os.environ)


@pytest.fixture(scope="session")
def live_settings() -> LiveSettings:
    return _SETTINGS


@pytest.fixture
def pause_world(
    tmp_path: Path, amoeba_home: Path, live_settings: LiveSettings
) -> Iterator[PauseWorld]:
    """A fresh member and program under the test's own ``AMOEBA_HOME``."""
    yield build_world(tmp_path, amoeba_home, live_settings)
