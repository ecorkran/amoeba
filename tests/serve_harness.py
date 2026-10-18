"""Shared helpers for the server tests. Nothing here binds off loopback."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from starlette.testclient import TestClient


@dataclass(frozen=True)
class TlsFiles:
    """A self-signed localhost certificate, its key, and a key that does not match."""

    certfile: Path
    keyfile: Path
    other_keyfile: Path


#: A TEST VALUE ONLY, never a real credential: 48 hex characters, as
#: ``openssl rand -hex 24`` would produce.
TEST_TOKEN = "0123456789abcdef" * 3

#: Every request the test client sends goes to this loopback origin.
BASE_URL = "http://127.0.0.1"

#: ``make_client(token=None, settings=None, *, raise_server_exceptions=True)``.
type ClientFactory = Callable[..., TestClient]
