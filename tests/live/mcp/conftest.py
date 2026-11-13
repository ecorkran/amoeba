"""Fixtures for the MCP live test (slice 226, task 6.2).

Collected only when the tier is named (``uv run pytest tests/live/mcp``). It reuses
the pause tier's throwaway member and settings, so the same three ``AMOEBA_LIVE_*``
variables are read at collection and a missing one fails by name.
"""

from __future__ import annotations

from live.pause.conftest import live_settings, pause_world

__all__ = ["live_settings", "pause_world"]
