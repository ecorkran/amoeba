"""The one ``host:port`` parser (slice 260, D3)."""

from __future__ import annotations

from pathlib import Path

import pytest

from amoeba.client.client_file import ClientFile, load_client_file
from amoeba.client.errors import ClientFileError
from amoeba.wire.address import split_address
from amoeba.wire.join_line import JoinError, parse_join_line

BAD_ADDRESSES = [
    "no-port",
    ":8443",
    "host:",
    "host:port",
    "host:0",
    "host:65536",
    "host:-1",
    "ho st:8443",
    "host:84\n43",
    "host:٤٣",
]


def test_a_host_and_a_port_split() -> None:
    assert split_address("hub.example:8443") == ("hub.example", 8443)
    assert split_address("[::1]:65535") == ("::1", 65535)


@pytest.mark.parametrize("text", BAD_ADDRESSES)
def test_anything_else_is_refused(text: str) -> None:
    with pytest.raises(ValueError, match="host:port"):
        split_address(text)


@pytest.mark.parametrize("text", BAD_ADDRESSES)
def test_a_join_line_with_a_bad_address_is_refused(text: str) -> None:
    line = f"{text},{'a' * 64},some-token"

    with pytest.raises(JoinError, match="address"):
        parse_join_line(line)


@pytest.mark.parametrize("text", BAD_ADDRESSES)
def test_a_client_file_with_a_bad_address_is_refused_naming_the_key(
    tmp_path: Path, text: str
) -> None:
    certificate = tmp_path / "pinned.pem"
    certificate.write_text("pem", encoding="utf-8")
    path = tmp_path / "client.yaml"
    path.write_text(f"address: {text!r}\nmachine: alpha\ntoken: t\n", encoding="utf-8")
    path.chmod(0o600)

    with pytest.raises(ClientFileError, match="address"):
        load_client_file(path, certificate)


def test_a_client_file_model_refuses_a_bad_address() -> None:
    with pytest.raises(ValueError, match="host:port"):
        ClientFile(address="nowhere", machine="alpha", token="t")
