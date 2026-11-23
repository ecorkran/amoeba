"""`client.call` through the in-process hub, with short times (slice 260, D5-D10)."""

from __future__ import annotations

import http.server
import ssl
import threading
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

from amoeba.client import call as call_module
from amoeba.client.call import call
from amoeba.client.client_file import ClientFile
from amoeba.client.errors import (
    HubCertificateError,
    HubRefusedError,
    HubUnreachableError,
)
from amoeba.hub.calls import DoorHooks
from amoeba.hub.certificate import make_certificate
from amoeba.wire.protocol import RefusalCode
from amoeba.wire.times import DOOR_VERSION, DoorTimes
from hub.call_support import ALPHA_TOKEN
from hub.in_process_hub import InProcessHub

SHORT = DoorTimes(
    connect_seconds=1.0, read_seconds=2.0, retry_seconds=0.6, retry_pause_seconds=0.1
)


@pytest.fixture
def hub(tmp_path: Path) -> Iterator[InProcessHub]:
    with InProcessHub(tmp_path) as running:
        yield running


def _client(hub: InProcessHub, token: str = ALPHA_TOKEN) -> ClientFile:
    return ClientFile(address=hub.address, machine="alpha", token=token)


def _standing(hub: InProcessHub, call_id: str, times: DoorTimes = SHORT) -> object:
    return call(
        _client(hub),
        hub.cert_path,
        "standing",
        {"text": "a ruling"},
        times,
        call_id=call_id,
    )


def test_a_served_call_returns_its_result_document(hub: InProcessHub) -> None:
    result = call(_client(hub), hub.cert_path, "decisions", {}, SHORT)

    assert result["outcome"] == "listed"


def test_a_refusal_raises_hub_refused_with_its_code_and_the_two_commands(
    hub: InProcessHub,
) -> None:
    with pytest.raises(HubRefusedError) as raised:
        call(_client(hub, "wrong-token"), hub.cert_path, "decisions", {}, SHORT)

    assert raised.value.code is RefusalCode.BAD_TOKEN
    assert "amoeba hub invite alpha" in str(raised.value)
    assert "amoeba join" in str(raised.value)
    assert hub.address in str(raised.value)
    assert "wrong-token" not in str(raised.value)


def test_a_hub_with_another_certificate_fails_at_once_without_retrying(
    hub: InProcessHub, tmp_path: Path
) -> None:
    other = tmp_path / "other-cert.pem"
    make_certificate(other, tmp_path / "other-key.pem")
    began = time.monotonic()

    with pytest.raises(HubCertificateError) as raised:
        call(_client(hub), other, "decisions", {}, SHORT)

    assert time.monotonic() - began < SHORT.retry_seconds
    assert "amoeba join --address" in str(raised.value)
    assert "amoeba hub invite" in str(raised.value)


def test_a_stopped_hub_is_unreachable_with_unknown_and_advice_for_a_writing_call(
    hub: InProcessHub,
) -> None:
    hub.stop()

    with pytest.raises(HubUnreachableError) as writing:
        _standing(hub, "c1")
    with pytest.raises(HubUnreachableError) as reading:
        call(_client(hub), hub.cert_path, "decisions", {}, SHORT)

    assert hub.address in str(writing.value)
    assert "outcome of this call is unknown" in str(writing.value)
    assert "Run it again with the same text" in str(writing.value)
    assert "amoeba join --address" in str(writing.value)
    assert "unknown" not in str(reading.value)
    assert "amoeba join --address" in str(reading.value)


def test_a_dropped_reply_then_a_new_server_returns_the_first_result_once(
    tmp_path: Path,
) -> None:
    class DropTheReply(Exception):
        pass

    def drop() -> None:
        raise DropTheReply

    with InProcessHub(tmp_path, DoorHooks(after_commit=drop)) as hub:
        with pytest.raises(HubUnreachableError):
            _standing(hub, "same-call")
        hub.stop()
        hub.hooks = DoorHooks()
        hub.start()

        again = _standing(hub, "same-call")

        assert isinstance(again, dict) and again["outcome"] == "given"
        count = hub.rig.rows("SELECT COUNT(*) FROM standing_answers")
        assert count == [(1,)]


def test_a_client_with_another_door_version_gets_both_versions_and_the_upgrade(
    hub: InProcessHub, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(call_module, "DOOR_VERSION", DOOR_VERSION + 1)

    with pytest.raises(HubRefusedError) as raised:
        call(_client(hub), hub.cert_path, "decisions", {}, SHORT)

    assert raised.value.code is RefusalCode.DOOR_VERSION
    assert str(DOOR_VERSION) in str(raised.value)
    assert str(DOOR_VERSION + 1) in str(raised.value)
    assert "uv tool install --force amoeba-ai" in str(raised.value)


def test_a_reply_header_with_another_version_raises_the_same_error(
    hub: InProcessHub, monkeypatch: pytest.MonkeyPatch
) -> None:
    from amoeba.hub import app

    monkeypatch.setattr(app, "DOOR_VERSION", DOOR_VERSION + 5)

    with pytest.raises(HubRefusedError) as raised:
        call(_client(hub), hub.cert_path, "decisions", {}, SHORT)

    assert raised.value.code is RefusalCode.DOOR_VERSION
    assert "uv tool install --force amoeba-ai" in str(raised.value)


def test_a_hub_answering_non_reply_bodies_counts_as_no_reply(tmp_path: Path) -> None:
    cert, key = tmp_path / "cert.pem", tmp_path / "key.pem"
    make_certificate(cert, key)
    attempts: list[int] = []

    class NotAReply(http.server.BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            attempts.append(1)
            self.rfile.read(int(self.headers.get("Content-Length", "0")))
            body = b"<html>502 Bad Gateway</html>"
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            return None

    server = http.server.HTTPServer(("127.0.0.1", 0), NotAReply)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert, key)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        client = ClientFile(
            address=f"127.0.0.1:{server.server_port}", machine="alpha", token="t"
        )
        with pytest.raises(HubUnreachableError):
            call(client, cert, "decisions", {}, SHORT)
    finally:
        server.shutdown()
        worker.join(5)

    assert len(attempts) >= 2
