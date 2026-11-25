"""The session headers a tick and an exit carry (slice 263, D6)."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import pytest

from amoeba.client import call as call_module
from amoeba.client.client_file import ClientFile
from amoeba.client.errors import HubUnreachableError
from amoeba.wire.protocol import (
    HEADER_SESSION_CLIENT,
    HEADER_SESSION_DIRECTORY,
    HEADER_SESSION_ID,
    HEADER_SESSION_PROJECT,
    SessionIdentity,
)
from amoeba.wire.times import TICK_TIMES

CLIENT = ClientFile(address="hub.example:8443", machine="alpha", token="t0k3n")
SESSION = "ab" * 16


def _identity(project: str | None = "proj-1") -> SessionIdentity:
    return SessionIdentity(SESSION, project, "claude-code", "/work/my repo/é")


@pytest.fixture
def sent(monkeypatch: pytest.MonkeyPatch) -> list[Mapping[str, str]]:
    """Every attempt's headers; each attempt gets no reply."""
    seen: list[Mapping[str, str]] = []

    def attempt(*args: object) -> tuple[bytes, str | None]:
        headers = args[4]
        assert isinstance(headers, dict)
        seen.append(headers)  # type: ignore[arg-type]
        raise OSError("no reply")

    def no_context(_path: Path) -> None:
        return None

    monkeypatch.setattr(call_module, "pinned_context", no_context)
    monkeypatch.setattr(call_module, "_attempt", attempt)
    return seen


def _call(identity: SessionIdentity | None) -> None:
    with pytest.raises(HubUnreachableError):
        call_module.call(
            CLIENT, Path("cert"), "session_tick", {}, TICK_TIMES, identity=identity
        )


def test_the_four_headers_are_sent_with_the_directory_percent_encoded(
    sent: list[Mapping[str, str]],
) -> None:
    _call(_identity())

    (headers,) = sent
    assert headers[HEADER_SESSION_ID] == SESSION
    assert headers[HEADER_SESSION_PROJECT] == "proj-1"
    assert headers[HEADER_SESSION_CLIENT] == "claude-code"
    assert headers[HEADER_SESSION_DIRECTORY] == "/work/my%20repo/%C3%A9"


def test_the_project_header_is_absent_for_a_non_project(
    sent: list[Mapping[str, str]],
) -> None:
    _call(_identity(project=None))

    (headers,) = sent
    assert HEADER_SESSION_PROJECT not in headers
    assert HEADER_SESSION_ID in headers


def test_a_call_with_no_identity_sends_none_of_them(
    sent: list[Mapping[str, str]],
) -> None:
    _call(None)

    (headers,) = sent
    assert not [name for name in headers if name.startswith("Amoeba-Session-")]


def test_the_tick_makes_one_attempt(sent: list[Mapping[str, str]]) -> None:
    _call(_identity())

    assert len(sent) == 1
