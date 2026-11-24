"""The web app through the in-process hub: lengths, statuses, the version header."""

from __future__ import annotations

import http.client
import json
import ssl
from collections.abc import Iterator
from pathlib import Path

import pytest

from amoeba.wire.fingerprint import fingerprint
from amoeba.wire.protocol import (
    DOCUMENT_KEY,
    HEADER_AUTHORIZATION,
    HEADER_CALL_ID,
    HEADER_CLIENT_VERSION,
    HEADER_DOOR_VERSION,
    MAX_CALL_BYTES,
    REFUSAL_STATUS,
    DoneReply,
    RefusalCode,
    RefusedReply,
    parse_reply,
)
from amoeba.wire.times import DOOR_VERSION
from hub.call_support import ALPHA_TOKEN, CLIENT_VERSION
from hub.in_process_hub import InProcessHub


@pytest.fixture
def hub(tmp_path: Path) -> Iterator[InProcessHub]:
    with InProcessHub(tmp_path) as running:
        yield running


def _connection(hub: InProcessHub) -> http.client.HTTPSConnection:
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_REQUIRED
    context.load_verify_locations(cafile=hub.cert_path)
    return http.client.HTTPSConnection(
        "127.0.0.1", hub.port, context=context, timeout=5
    )


def _post(
    hub: InProcessHub,
    name: str,
    body: bytes | None,
    headers: dict[str, str] | None = None,
) -> tuple[int, dict[str, str], bytes]:
    sent = {
        HEADER_AUTHORIZATION: f"Bearer {ALPHA_TOKEN}",
        HEADER_DOOR_VERSION: str(DOOR_VERSION),
        HEADER_CLIENT_VERSION: CLIENT_VERSION,
        HEADER_CALL_ID: "c1",
    }
    sent.update(headers or {})
    connection = _connection(hub)
    try:
        connection.request("POST", f"/call/{name}", body=body, headers=sent)
        response = connection.getresponse()
        return response.status, dict(response.getheaders()), response.read()
    finally:
        connection.close()


def _hello_body() -> bytes:
    return json.dumps({DOCUMENT_KEY: {}}).encode("utf-8")


def test_a_hello_over_pinned_tls_gets_done(hub: InProcessHub) -> None:
    status, _headers, body = _post(hub, "hello", _hello_body())

    assert status == 200
    reply = parse_reply(body)
    assert isinstance(reply, DoneReply)
    assert reply.result == {"machine": "alpha", "work": False}
    assert fingerprint(hub.cert_path.read_text(encoding="utf-8"))


def test_an_over_size_length_is_malformed_with_the_body_unread(
    hub: InProcessHub,
) -> None:
    status, _headers, body = _post(
        hub, "hello", None, {"Content-Length": str(MAX_CALL_BYTES + 1)}
    )

    reply = parse_reply(body)
    assert isinstance(reply, RefusedReply)
    assert reply.code is RefusalCode.MALFORMED_CALL
    assert status == 400


def test_a_missing_length_is_malformed(hub: InProcessHub) -> None:
    connection = _connection(hub)
    try:
        connection.putrequest("POST", "/call/hello")
        connection.putheader(HEADER_AUTHORIZATION, f"Bearer {ALPHA_TOKEN}")
        connection.putheader("Transfer-Encoding", "chunked")
        connection.endheaders()
        connection.send(b"2\r\n{}\r\n0\r\n\r\n")
        response = connection.getresponse()
        reply = parse_reply(response.read())
    finally:
        connection.close()

    assert isinstance(reply, RefusedReply)
    assert reply.code is RefusalCode.MALFORMED_CALL
    assert response.status == 400


@pytest.mark.parametrize(
    ("code", "request_kwargs"),
    [
        (RefusalCode.BAD_TOKEN, {"headers": {HEADER_AUTHORIZATION: "Bearer nope"}}),
        (RefusalCode.DOOR_VERSION, {"headers": {HEADER_DOOR_VERSION: "99"}}),
        (RefusalCode.MALFORMED_CALL, {"body": b"not json"}),
        (RefusalCode.NOT_SERVED, {"name": "handle_pause"}),
    ],
)
def test_each_refusal_travels_with_its_status(
    hub: InProcessHub, code: RefusalCode, request_kwargs: dict[str, object]
) -> None:
    name = str(request_kwargs.get("name", "hello"))
    body = request_kwargs.get("body", _hello_body())
    headers = request_kwargs.get("headers")
    assert isinstance(body, bytes)

    status, _headers, raw = _post(hub, name, body, headers)  # type: ignore[arg-type]

    reply = parse_reply(raw)
    assert isinstance(reply, RefusedReply)
    assert reply.code is code
    assert status == REFUSAL_STATUS[code]


def test_every_reply_has_the_door_version_header(hub: InProcessHub) -> None:
    replies = [
        _post(hub, "hello", _hello_body()),
        _post(hub, "hello", None, {"Content-Length": str(MAX_CALL_BYTES + 1)}),
        _post(hub, "handle_pause", _hello_body()),
    ]

    for _status, headers, _body in replies:
        lowered = {key.lower(): value for key, value in headers.items()}
        assert lowered[HEADER_DOOR_VERSION.lower()] == str(DOOR_VERSION)
