"""``amoeba_home`` and the paths under it (slice 222, D1 and D10)."""

from __future__ import annotations

from pathlib import Path

import pytest

from amoeba.config.home import (
    CONFIG_FILE_NAME,
    HOME_VARIABLE,
    STORE_FILE_NAME,
    AmoebaHomeError,
    answering_dir,
    config_path,
    logs_dir,
    squadron_runs_dir,
    store_path,
)
from amoeba.config.home import amoeba_home as resolved_home


def test_paths_sit_under_the_variable(amoeba_home: Path) -> None:
    assert store_path() == amoeba_home / STORE_FILE_NAME
    assert config_path() == amoeba_home / CONFIG_FILE_NAME
    assert store_path().name == "amoeba.sqlite3"
    assert config_path().name == "config.yaml"


def test_the_fixtures_home_is_not_the_real_default(amoeba_home: Path) -> None:
    assert resolved_home() == amoeba_home
    assert amoeba_home != Path.home() / ".config" / "amoeba"


def test_unset_uses_the_default_and_ignores_xdg(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv(HOME_VARIABLE)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))

    assert resolved_home() == Path.home() / ".config" / "amoeba"


@pytest.mark.parametrize("value", ["", "   ", "relative/dir", "."])
def test_empty_or_relative_value_raises(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv(HOME_VARIABLE, value)

    with pytest.raises(AmoebaHomeError, match=HOME_VARIABLE):
        resolved_home()


def test_answering_and_logs_dirs_sit_under_the_variable(amoeba_home: Path) -> None:
    assert answering_dir() == amoeba_home / "answering"
    assert logs_dir() == amoeba_home / "logs"


def test_squadron_runs_dir_sits_under_the_user_home(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))

    assert squadron_runs_dir() == tmp_path / ".config" / "squadron" / "runs"
