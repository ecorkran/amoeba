"""Shared fixtures for the MCP server tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from amoeba.mcp import tick as tick_module
from mcp_server.presence_rig import PEER, seed_member


@pytest.fixture
def store_path(tmp_path: Path) -> Path:
    """A throwaway store with the member and ``PEER``."""
    path = tmp_path / "amoeba.sqlite3"
    seed_member(path)
    seed_member(path, PEER)
    return path


@pytest.fixture(autouse=True)
def short_wait_before_the_first_reply(monkeypatch: pytest.MonkeyPatch) -> None:
    """The real wait is five seconds; a failing tick here retries in milliseconds."""
    monkeypatch.setattr(tick_module, "TICK_SECONDS_BEFORE_FIRST_REPLY", 0.01)
