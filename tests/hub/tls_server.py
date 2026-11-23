"""A TLS listener that records every application byte it reads (slice 260, D5).

It proves what a client sent: a client that does not trust the certificate must fail the
handshake having sent nothing, and `join`'s certificate fetch must send no request.
"""

from __future__ import annotations

import socket
import ssl
import threading
from pathlib import Path

LOOPBACK = "127.0.0.1"
ACCEPT_POLL_SECONDS = 0.1
READ_SECONDS = 0.5


class RecordingTlsServer:
    def __init__(self, cert_path: Path, key_path: Path, host: str = LOOPBACK) -> None:
        self._host = host
        self._context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        self._context.load_cert_chain(cert_path, key_path)
        family = socket.AF_INET6 if ":" in host else socket.AF_INET
        self._listener = socket.socket(family)
        self._listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._listener.bind((host, 0))
        self._listener.listen()
        self._listener.settimeout(ACCEPT_POLL_SECONDS)
        self.port: int = self._listener.getsockname()[1]
        self.received = bytearray()
        self.handshakes_completed = 0
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._serve, daemon=True)

    @property
    def address(self) -> str:
        shown = f"[{self._host}]" if ":" in self._host else self._host
        return f"{shown}:{self.port}"

    def __enter__(self) -> RecordingTlsServer:
        self._thread.start()
        return self

    def __exit__(self, *_exc: object) -> None:
        self._stop.set()
        self._thread.join(5)
        self._listener.close()

    def _serve(self) -> None:
        while not self._stop.is_set():
            try:
                connection, _peer = self._listener.accept()
            except TimeoutError:
                continue
            with connection:
                self._handle(connection)

    def _handle(self, connection: socket.socket) -> None:
        try:
            secure = self._context.wrap_socket(connection, server_side=True)
        except (ssl.SSLError, OSError):
            # A handshake that fails is the point of some tests: nothing was read.
            return
        with secure:
            self.handshakes_completed += 1
            secure.settimeout(READ_SECONDS)
            while True:
                try:
                    data = secure.recv(4096)
                except (TimeoutError, ssl.SSLError, OSError):
                    return
                if not data:
                    return
                self.received.extend(data)
