"""A scanner or a broken peer fills no stream and no disk (slice 260, D16)."""

from __future__ import annotations

import os
import socket
import ssl
from pathlib import Path

from hub_fixture import FIRST, FixtureHub, two_machine_hub

REPEATS = 60
LOG_FILES_KEPT = 3
LOG_MAX_BYTES = 3000
PLAIN_HTTP = b"GET / HTTP/1.1\r\nHost: hub\r\n\r\n"
MALFORMED_HTTP = b"BAD\x00METHOD /call/hello HTTP/9.9\r\nno colon here\r\n\r\n\xff\xfe"


def _send_raw(hub: FixtureHub, data: bytes) -> None:
    with socket.create_connection(("127.0.0.1", hub.port), timeout=5) as raw:
        raw.sendall(data)


def _send_inside_tls(hub: FixtureHub, data: bytes) -> None:
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    with socket.create_connection(("127.0.0.1", hub.port), timeout=5) as raw:
        with context.wrap_socket(raw) as secure:
            secure.sendall(data)
            secure.settimeout(1)
            try:
                secure.recv(4096)
            except (TimeoutError, ssl.SSLError, OSError):
                # The hub may answer 400 or close; either is fine here.
                pass


def test_noise_leaves_stderr_with_only_the_serving_line_and_the_log_in_bounds(
    tmp_path: Path,
) -> None:
    with two_machine_hub(
        tmp_path, hub_log_max_bytes=LOG_MAX_BYTES, hub_logs_kept=LOG_FILES_KEPT
    ) as hub:
        for number in range(REPEATS):
            _send_raw(hub, os.urandom(32 + number * 16))
            _send_raw(hub, PLAIN_HTTP)
            _send_inside_tls(hub, MALFORMED_HTTP)

        done = hub.clients[FIRST].run("decisions", "-j")

        assert done.code == 0, done.err
        assert len(hub.stderr_lines) == 1 and "serving on" in hub.stderr_lines[0]
        assert hub.stdout_lines == []
        log_files = list(hub.layout.hub_log.parent.iterdir())
        assert 1 <= len(log_files) <= LOG_FILES_KEPT
        assert sum(path.stat().st_size for path in log_files) > 0  # it went to the log
