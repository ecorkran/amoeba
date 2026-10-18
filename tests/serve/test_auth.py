"""The request guard: token, Origin, Host, content type, and token secrecy."""

from __future__ import annotations

import logging

import pytest
from httpx2 import Response
from inspection_harness import PROJECT, SeededStore
from serve_harness import TEST_TOKEN, ClientFactory

from amoeba.serve.auth import host_name, media_type

_NODES = "/v1/listings/nodes"
_NODES_QUERY = {"project": PROJECT}
_GOOD = {"Authorization": f"Bearer {TEST_TOKEN}"}
_WRONG = {"Authorization": "Bearer " + "f" * len(TEST_TOKEN)}

#: Every route the server has or will have. The guard refuses before routing.
_EVERY_ROUTE = [
    ("GET", "/v1/listings/nodes"),
    ("POST", "/v1/projects/p/submissions"),
    ("GET", "/v1/projects/p/submissions/s"),
    ("GET", "/v1/projects/p/feed"),
]


def _error(response: Response) -> str:
    return str(response.json()["error"])


def test_a_correct_token_is_served(
    seeded: SeededStore, make_client: ClientFactory
) -> None:
    response = make_client(TEST_TOKEN).get(_NODES, params=_NODES_QUERY, headers=_GOOD)

    assert response.status_code == 200


def test_missing_and_wrong_tokens_get_the_same_401(
    seeded: SeededStore, make_client: ClientFactory
) -> None:
    client = make_client(TEST_TOKEN)
    missing = client.get(_NODES, params=_NODES_QUERY)
    wrong = client.get(_NODES, params=_NODES_QUERY, headers=_WRONG)

    for response in (missing, wrong):
        assert response.status_code == 401
        assert response.headers["www-authenticate"] == "Bearer"
        assert _error(response) == "unauthorized"
    assert missing.content == wrong.content


def test_without_a_token_loopback_requests_pass(
    seeded: SeededStore, make_client: ClientFactory
) -> None:
    assert make_client().get(_NODES, params=_NODES_QUERY).status_code == 200


@pytest.mark.parametrize(("method", "path"), _EVERY_ROUTE)
@pytest.mark.parametrize("headers", [{}, _WRONG], ids=["missing", "wrong"])
def test_401_on_every_endpoint(
    make_client: ClientFactory, method: str, path: str, headers: dict[str, str]
) -> None:
    response = make_client(TEST_TOKEN).request(
        method, path, headers={"content-type": "application/json", **headers}
    )

    assert response.status_code == 401
    assert _error(response) == "unauthorized"


def test_an_origin_header_is_403(
    seeded: SeededStore, make_client: ClientFactory
) -> None:
    response = make_client().get(
        _NODES, params=_NODES_QUERY, headers={"origin": "http://127.0.0.1"}
    )

    assert response.status_code == 403
    assert _error(response) == "origin_not_allowed"


def test_origin_is_checked_before_the_token(make_client: ClientFactory) -> None:
    response = make_client(TEST_TOKEN).get(
        _NODES, headers={"origin": "https://evil.example", **_WRONG}
    )

    assert response.status_code == 403


def test_a_foreign_host_on_loopback_is_421(make_client: ClientFactory) -> None:
    response = make_client().get(_NODES, headers={"host": "evil.example"})

    assert response.status_code == 421
    assert _error(response) == "host_not_allowed"


@pytest.mark.parametrize(
    "host", ["localhost:8765", "127.0.0.1", "[::1]:8765", "LOCALHOST"]
)
def test_loopback_host_names_pass(
    seeded: SeededStore, make_client: ClientFactory, host: str
) -> None:
    response = make_client().get(_NODES, params=_NODES_QUERY, headers={"host": host})

    assert response.status_code == 200


@pytest.mark.parametrize(
    ("host", "name"),
    [
        ("localhost:8765", "localhost"),
        ("127.0.0.1", "127.0.0.1"),
        ("[::1]:8765", "::1"),
        ("[::1]", "::1"),
        ("evil.example:80", "evil.example"),
    ],
)
def test_host_name_strips_the_port(host: str, name: str) -> None:
    assert host_name(host) == name


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("application/json", "application/json"),
        ("Application/JSON; charset=utf-8", "application/json"),
        ("text/plain", "text/plain"),
        ("", ""),
    ],
)
def test_media_type_drops_parameters(value: str, expected: str) -> None:
    assert media_type(value) == expected


def test_a_post_that_is_not_json_is_415(make_client: ClientFactory) -> None:
    response = make_client().post(
        "/v1/projects/p/submissions",
        content=b"x",
        headers={"content-type": "text/plain"},
    )

    assert response.status_code == 415
    assert _error(response) == "unsupported_media_type"


def test_the_token_appears_in_no_log_record_or_response(
    seeded: SeededStore, make_client: ClientFactory, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    client = make_client(TEST_TOKEN)
    responses = [
        client.get(_NODES, params=_NODES_QUERY, headers=_GOOD),
        client.get(_NODES, params=_NODES_QUERY, headers=_WRONG),
        client.get(_NODES, params=_NODES_QUERY),
        client.get("/v1/listings/not-a-listing", headers=_GOOD),
    ]

    for record in caplog.records:
        assert TEST_TOKEN not in record.getMessage()
        assert TEST_TOKEN not in repr(record.args)
    for response in responses:
        assert TEST_TOKEN not in response.text
        assert all(TEST_TOKEN not in value for value in response.headers.values())
