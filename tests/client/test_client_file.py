"""The client file: three keys, mode 0600, a saved certificate (slice 260, D3)."""

from __future__ import annotations

import stat
from pathlib import Path

import pytest

from amoeba.client.client_file import (
    ClientFile,
    load_client_file,
    read_client_address,
    write_client_file,
)
from amoeba.client.errors import ClientFileError

CLIENT = ClientFile(address="hub.example:8443", machine="alpha", token="t0k3n-value")


@pytest.fixture
def paths(tmp_path: Path) -> tuple[Path, Path]:
    cert = tmp_path / "pinned-hub-cert.pem"
    cert.write_text("not really a certificate", encoding="utf-8")
    return tmp_path / "client.yaml", cert


def test_write_then_load_round_trips_and_the_file_is_0600(
    paths: tuple[Path, Path],
) -> None:
    client_path, cert = paths

    write_client_file(client_path, CLIENT)

    assert stat.S_IMODE(client_path.stat().st_mode) == 0o600
    assert load_client_file(client_path, cert) == CLIENT


def test_a_write_leaves_no_temporary_file_and_replaces_an_old_one(
    paths: tuple[Path, Path],
) -> None:
    client_path, cert = paths
    leftover = client_path.with_name("client.yaml.tmp")
    leftover.write_text("stale", encoding="utf-8")
    leftover.chmod(0o644)

    write_client_file(client_path, CLIENT)

    assert not leftover.exists()
    assert load_client_file(client_path, cert) == CLIENT


def test_a_file_others_can_read_fails_with_the_chmod_command(
    paths: tuple[Path, Path],
) -> None:
    client_path, cert = paths
    write_client_file(client_path, CLIENT)
    client_path.chmod(0o640)

    with pytest.raises(ClientFileError) as raised:
        load_client_file(client_path, cert)

    assert f"chmod 600 {client_path}" in str(raised.value)
    assert CLIENT.token not in str(raised.value)


def test_a_missing_key_names_it(paths: tuple[Path, Path]) -> None:
    client_path, cert = paths
    client_path.write_text("address: h:1\nmachine: alpha\n", encoding="utf-8")
    client_path.chmod(0o600)

    with pytest.raises(ClientFileError, match="token") as raised:
        load_client_file(client_path, cert)

    assert str(client_path) in str(raised.value)


def test_an_unknown_key_names_it(paths: tuple[Path, Path]) -> None:
    client_path, cert = paths
    client_path.write_text(
        "address: h:1\nmachine: alpha\ntoken: x\nextra_key: 1\n", encoding="utf-8"
    )
    client_path.chmod(0o600)

    with pytest.raises(ClientFileError, match="extra_key"):
        load_client_file(client_path, cert)


def test_a_missing_certificate_names_it_and_says_to_join_again(
    paths: tuple[Path, Path],
) -> None:
    client_path, cert = paths
    write_client_file(client_path, CLIENT)
    cert.unlink()

    with pytest.raises(ClientFileError) as raised:
        load_client_file(client_path, cert)

    assert str(cert) in str(raised.value)
    assert "amoeba join" in str(raised.value)
    assert "amoeba hub invite" in str(raised.value)


def test_read_client_address_works_with_no_certificate(
    paths: tuple[Path, Path],
) -> None:
    client_path, cert = paths
    write_client_file(client_path, CLIENT)
    cert.unlink()

    assert read_client_address(client_path) == CLIENT.address


def test_a_file_that_is_not_a_mapping_is_an_error(paths: tuple[Path, Path]) -> None:
    client_path, cert = paths
    client_path.write_text("- a\n- b\n", encoding="utf-8")
    client_path.chmod(0o600)

    with pytest.raises(ClientFileError, match="mapping"):
        load_client_file(client_path, cert)
