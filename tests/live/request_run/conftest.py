"""Fixtures for the live slice-writing tests (slice 180, D10).

The settings are read at collection: a missing variable fails the whole sub-tier
with its name. Provider keys come from the environment of the test run.
"""

from __future__ import annotations

import os

import pytest
from live_request_settings import RequestLiveSettings, read_request_live_settings

_SETTINGS = read_request_live_settings(os.environ)


@pytest.fixture(scope="session")
def request_live_settings() -> RequestLiveSettings:
    return _SETTINGS
