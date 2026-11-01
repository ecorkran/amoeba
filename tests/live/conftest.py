"""The live tier: real ``sq``, real models, real spend (slice 140, D10).

``--ignore=tests/live`` keeps a bare ``uv run pytest`` out of this directory, so
this file loads only when the tier is named: ``uv run pytest tests/live``.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# The tier's shared modules live beside the other harnesses in ``tests/``.
_TESTS_DIRECTORY = str(Path(__file__).parent.parent)
if _TESTS_DIRECTORY not in sys.path:
    sys.path.insert(0, _TESTS_DIRECTORY)

from live_settings import LiveSettings, read_live_settings  # noqa: E402

# Read at collection: a missing variable fails the whole tier with its name.
_SETTINGS = read_live_settings(os.environ)


@pytest.fixture(scope="session")
def live_settings() -> LiveSettings:
    return _SETTINGS
