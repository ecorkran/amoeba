"""The paths the hub and the client add to the homes (slice 260, D1)."""

from __future__ import annotations

from pathlib import Path

import pytest

from amoeba.config import home


def test_every_hub_and_client_file_is_under_its_home(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv(home.HOME_VARIABLE, str(tmp_path))

    layout = home.state_layout()

    assert layout.client_file == tmp_path / "client.yaml"
    assert layout.hub_file == tmp_path / "hub.yaml"
    assert layout.pinned_cert == tmp_path / "pinned-hub-cert.pem"
    assert layout.hub_cert == tmp_path / "hub-cert.pem"
    assert layout.hub_key == tmp_path / "hub-key.pem"
    assert layout.hub_log == tmp_path / "logs" / "hub" / "hub.log"


def test_without_the_override_the_client_file_is_config_and_the_certificate_state(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv(home.HOME_VARIABLE)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    assert home.client_file_path() == tmp_path / ".config" / "amoeba" / "client.yaml"
    assert home.hub_file_path() == tmp_path / ".config" / "amoeba" / "hub.yaml"
    assert (
        home.pinned_cert_path()
        == tmp_path / ".local" / "state" / "amoeba" / "pinned-hub-cert.pem"
    )


def test_the_layout_builder_agrees_with_every_path_function(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv(home.HOME_VARIABLE, str(tmp_path))

    built = home.layout_under(home.state_home(), home.config_home(), None)

    assert built == home.state_layout()
    assert built.store_path == home.store_path()
    assert built.answering_dir == home.answering_dir()
    assert built.logs_dir == home.logs_dir()
    assert built.calls_log_dir == home.calls_log_dir()
    assert built.client_file == home.client_file_path()
    assert built.hub_file == home.hub_file_path()
    assert built.pinned_cert == home.pinned_cert_path()
    assert built.hub_cert == home.hub_cert_path()
    assert built.hub_key == home.hub_key_path()
    assert built.hub_log == home.hub_log_path()
