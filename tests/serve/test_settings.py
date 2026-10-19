"""``ServeSettings``: the LLD's defaults, and refusal of unusable values."""

from __future__ import annotations

import dataclasses

import pytest

from amoeba.feed import FeedSettings
from amoeba.serve.settings import MIN_TOKEN_LENGTH, TOKEN_ENV_VAR, ServeSettings


def test_defaults_are_the_lld_values() -> None:
    settings = ServeSettings()

    assert settings.host == "127.0.0.1"
    assert settings.port == 8765
    assert settings.tls_certfile is None
    assert settings.tls_keyfile is None
    assert settings.heartbeat_interval_seconds == 15.0
    assert settings.send_timeout_seconds == 30.0
    assert settings.max_streams == 32
    assert settings.max_request_bytes == 1_048_576
    assert settings.shutdown_grace_seconds == 5
    assert settings.feed == FeedSettings()


def test_exactly_ten_fields_and_no_token() -> None:
    names = [f.name for f in dataclasses.fields(ServeSettings)]

    assert len(names) == 10
    assert not any("token" in name for name in names)


def test_token_constants() -> None:
    assert TOKEN_ENV_VAR == "AMOEBA_SERVE_TOKEN"
    assert MIN_TOKEN_LENGTH == 32


@pytest.mark.parametrize(
    "name",
    [
        "heartbeat_interval_seconds",
        "send_timeout_seconds",
        "max_streams",
        "max_request_bytes",
        "shutdown_grace_seconds",
    ],
)
@pytest.mark.parametrize("value", [0, -1])
def test_a_non_positive_limit_is_refused(name: str, value: int) -> None:
    with pytest.raises(ValueError, match=name):
        ServeSettings(**{name: value})  # pyright: ignore[reportArgumentType]


@pytest.mark.parametrize("port", [-1, 65536])
def test_a_port_out_of_range_is_refused(port: int) -> None:
    with pytest.raises(ValueError, match="port"):
        ServeSettings(port=port)


@pytest.mark.parametrize("port", [0, 65535])
def test_the_port_bounds_are_allowed(port: int) -> None:
    assert ServeSettings(port=port).port == port
