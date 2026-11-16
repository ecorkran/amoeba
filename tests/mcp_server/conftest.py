"""Shared fixtures for the MCP server tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from mcp_server.presence_rig import PEER, seed_member


@pytest.fixture
def store_path(tmp_path: Path) -> Path:
    """A throwaway store with the member and ``PEER``."""
    path = tmp_path / "amoeba.sqlite3"
    seed_member(path)
    seed_member(path, PEER)
    return path
