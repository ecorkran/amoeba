"""Errors of starting the hub (slice 260). Reported by `amoeba hub serve` with exit 3;
they do not cross ``wiring``."""

from __future__ import annotations


class HubStartError(Exception):
    """The hub cannot start; the message is one line saying why and what to do."""
