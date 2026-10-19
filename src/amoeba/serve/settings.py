"""Every tunable the server has, defined exactly once.

Like ``ProcessSettings``, there is no fallback default at any call site and no
environment read for a tunable. The one environment read is the token, which is
a credential and not a tunable (``process-contract.md``): it is never a field
here, so it can never be logged with the settings.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

from amoeba.feed import FeedSettings

#: The environment variable the bearer token is read from, once, at start-up.
TOKEN_ENV_VAR: Final = "AMOEBA_SERVE_TOKEN"

#: The shortest token accepted. It catches a short token, not a non-random one.
MIN_TOKEN_LENGTH: Final = 32

#: The highest TCP port. Port 0 asks the OS for an ephemeral one.
_MAX_PORT: Final = 65535


@dataclass(frozen=True)
class ServeSettings:
    """Tunables for ``amoeba serve``.

    Attributes:
        host: The address to bind. Loopback unless a token and TLS are set.
        port: The TCP port; 0 picks an ephemeral port (tests use it).
        tls_certfile: The TLS certificate, or ``None`` for plain HTTP.
        tls_keyfile: The TLS private key; set together with ``tls_certfile``.
        heartbeat_interval_seconds: How long an idle stream waits before sending
            a keepalive. A failed send is how a disconnect is noticed, so this
            bounds how long a closed client holds a stream slot.
        send_timeout_seconds: How long one stream send may block on a client
            that stopped reading before the stream is closed.
        max_streams: How many feed streams may be open at once, each holding one
            dedicated thread. The next stream gets 503.
        max_request_bytes: The largest request body read. A body that passes it
            gets 413, and reading stops at the chunk that passed it.
        shutdown_grace_seconds: How long shutdown waits for open connections
            before cancelling them. Set because an SSE stream never ends alone.
            Whole seconds: uvicorn's ``timeout_graceful_shutdown`` is an int.
        feed: The follow interval and batch size the streams use.
    """

    host: str = "127.0.0.1"
    port: int = 8765
    tls_certfile: Path | None = None
    tls_keyfile: Path | None = None
    heartbeat_interval_seconds: float = 15.0
    send_timeout_seconds: float = 30.0
    max_streams: int = 32
    max_request_bytes: int = 1_048_576
    shutdown_grace_seconds: int = 5
    feed: FeedSettings = field(default_factory=FeedSettings)

    def __post_init__(self) -> None:
        positive = {
            "heartbeat_interval_seconds": self.heartbeat_interval_seconds,
            "send_timeout_seconds": self.send_timeout_seconds,
            "max_streams": self.max_streams,
            "max_request_bytes": self.max_request_bytes,
            "shutdown_grace_seconds": self.shutdown_grace_seconds,
        }
        for name, value in positive.items():
            if value <= 0:
                raise ValueError(f"{name} must be positive, got {value}")
        if not 0 <= self.port <= _MAX_PORT:
            raise ValueError(f"port must be 0 to {_MAX_PORT}, got {self.port}")
