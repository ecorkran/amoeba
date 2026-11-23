"""The pinned connection and the one unverified fetch (slice 260, D5)."""

from __future__ import annotations

import socket
import ssl
import threading
import time
from contextlib import closing
from pathlib import Path

import pytest

from amoeba.client.errors import HubUnreachableError
from amoeba.client.trust import fetch_certificate, pinned_context
from amoeba.hub.certificate import make_certificate
from amoeba.wire.fingerprint import fingerprint
from hub.tls_server import LOOPBACK, RecordingTlsServer

CONNECT_SECONDS = 2.0
SETTLE_SECONDS = 0.3


def _hub_files(root: Path, name: str) -> tuple[Path, Path]:
    cert, key = root / f"{name}-cert.pem", root / f"{name}-key.pem"
    make_certificate(cert, key)
    return cert, key


def _connect(port: int, context: ssl.SSLContext) -> None:
    with (
        socket.create_connection((LOOPBACK, port), timeout=CONNECT_SECONDS) as raw,
        context.wrap_socket(raw),
    ):
        return None


def test_the_right_certificate_is_accepted(tmp_path: Path) -> None:
    cert, key = _hub_files(tmp_path, "right")
    with RecordingTlsServer(cert, key) as server:
        _connect(server.port, pinned_context(cert))
        time.sleep(SETTLE_SECONDS)

    assert server.handshakes_completed == 1
    assert bytes(server.received) == b""


def test_the_certificate_of_a_hub_at_an_ipv6_address_is_fetched(
    tmp_path: Path,
) -> None:
    cert, key = _hub_files(tmp_path, "ipv6")
    try:
        server = RecordingTlsServer(cert, key, host="::1")
    except OSError:
        pytest.skip("this machine has no IPv6 loopback")
    with server:
        pem = fetch_certificate(server.address, CONNECT_SECONDS)

    assert server.address.startswith("[::1]:")
    assert fingerprint(pem) == fingerprint(cert.read_text(encoding="utf-8"))


def test_another_certificate_fails_the_handshake_and_the_listener_reads_nothing(
    tmp_path: Path,
) -> None:
    served_cert, served_key = _hub_files(tmp_path, "served")
    other_cert, _other_key = _hub_files(tmp_path, "other")
    with RecordingTlsServer(served_cert, served_key) as server:
        with pytest.raises(ssl.SSLCertVerificationError):
            _connect(server.port, pinned_context(other_cert))
        time.sleep(SETTLE_SECONDS)

    assert bytes(server.received) == b""


def test_the_context_loads_no_system_certificates(tmp_path: Path) -> None:
    cert, _key = _hub_files(tmp_path, "only")

    context = pinned_context(cert)

    assert context.verify_mode is ssl.CERT_REQUIRED
    assert context.check_hostname is False
    assert context.cert_store_stats()["x509"] == 1


def test_fetch_returns_the_presented_certificate_and_sends_no_bytes(
    tmp_path: Path,
) -> None:
    cert, key = _hub_files(tmp_path, "fetched")
    with RecordingTlsServer(cert, key) as server:
        pem = fetch_certificate(server.address, CONNECT_SECONDS)
        time.sleep(SETTLE_SECONDS)

    assert fingerprint(pem) == fingerprint(cert.read_text(encoding="utf-8"))
    assert bytes(server.received) == b""


def test_nothing_listening_raises_hub_unreachable_naming_the_address() -> None:
    with closing(socket.socket()) as probe:
        probe.bind((LOOPBACK, 0))
        port = probe.getsockname()[1]
    address = f"{LOOPBACK}:{port}"

    with pytest.raises(HubUnreachableError, match=str(port)):
        fetch_certificate(address, CONNECT_SECONDS)


def test_a_peer_that_does_not_speak_tls_is_hub_unreachable() -> None:
    with closing(socket.socket()) as plain:
        plain.bind((LOOPBACK, 0))
        plain.listen()
        port = plain.getsockname()[1]
        plain.settimeout(CONNECT_SECONDS)

        def answer() -> None:
            connection, _ = plain.accept()
            with connection:
                connection.sendall(b"HTTP/1.1 400 not tls\r\n\r\n")
                time.sleep(SETTLE_SECONDS)

        worker = threading.Thread(target=answer, daemon=True)
        worker.start()
        with pytest.raises(HubUnreachableError):
            fetch_certificate(f"{LOOPBACK}:{port}", CONNECT_SECONDS)
        worker.join(5)
