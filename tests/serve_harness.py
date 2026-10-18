"""Shared helpers for the server tests. Nothing here binds off loopback."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TlsFiles:
    """A self-signed localhost certificate, its key, and a key that does not match."""

    certfile: Path
    keyfile: Path
    other_keyfile: Path
