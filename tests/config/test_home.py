"""The two homes and the paths under them (slice 222, D1 and D10; slice 228, D1)."""

from __future__ import annotations

from pathlib import Path

import pytest

from amoeba.config.home import (
    CONFIG_FILE_NAME,
    HOME_VARIABLE,
    STORE_FILE_NAME,
    AmoebaHomeError,
    answering_dir,
    calls_log_dir,
    config_home,
    config_path,
    legacy_state_home,
    logs_dir,
    squadron_runs_dir,
    state_home,
    state_layout,
    store_path,
)

XDG_VARIABLES = ("XDG_CONFIG_HOME", "XDG_STATE_HOME")


@pytest.fixture
def user_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """A throwaway ``HOME`` with ``AMOEBA_HOME`` unset."""
    monkeypatch.delenv(HOME_VARIABLE)
    monkeypatch.setenv("HOME", str(tmp_path))
    return tmp_path


def test_paths_sit_under_the_variable(amoeba_home: Path) -> None:
    assert store_path() == amoeba_home / STORE_FILE_NAME
    assert config_path() == amoeba_home / CONFIG_FILE_NAME
    assert store_path().name == "amoeba.sqlite3"
    assert config_path().name == "config.yaml"


def test_the_variable_overrides_both_homes_and_leaves_no_legacy_home(
    amoeba_home: Path,
) -> None:
    assert config_home() == amoeba_home
    assert state_home() == amoeba_home
    assert legacy_state_home() is None
    assert amoeba_home != Path.home() / ".config" / "amoeba"


def test_unset_gives_the_two_default_homes(user_home: Path) -> None:
    assert config_home() == user_home / ".config" / "amoeba"
    assert state_home() == user_home / ".local" / "state" / "amoeba"
    assert legacy_state_home() == user_home / ".config" / "amoeba"
    assert config_path() == config_home() / CONFIG_FILE_NAME
    assert store_path() == state_home() / STORE_FILE_NAME


def test_xdg_variables_change_nothing(
    monkeypatch: pytest.MonkeyPatch, user_home: Path
) -> None:
    before = (config_home(), state_home(), legacy_state_home())
    for variable in XDG_VARIABLES:
        monkeypatch.setenv(variable, str(user_home / "elsewhere"))

    assert (config_home(), state_home(), legacy_state_home()) == before


@pytest.mark.parametrize("value", ["", "   ", "relative/dir", "."])
def test_empty_or_relative_value_raises_from_every_home(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv(HOME_VARIABLE, value)

    for ask in (config_home, state_home, legacy_state_home, state_layout):
        with pytest.raises(AmoebaHomeError, match=HOME_VARIABLE):
            ask()


def test_answering_and_logs_dirs_sit_under_the_state_home(amoeba_home: Path) -> None:
    assert answering_dir() == amoeba_home / "answering"
    assert logs_dir() == amoeba_home / "logs"


def test_state_paths_leave_the_config_home_when_unset(user_home: Path) -> None:
    for state_path in (store_path(), answering_dir(), logs_dir(), calls_log_dir()):
        assert state_path.is_relative_to(state_home())
        assert not state_path.is_relative_to(config_home())


def test_calls_log_dir_is_under_the_logs(amoeba_home: Path) -> None:
    assert calls_log_dir() == logs_dir() / "calls"


def test_the_layout_holds_every_state_path(user_home: Path) -> None:
    layout = state_layout()

    assert layout.state_home == state_home()
    assert layout.store_path == store_path()
    assert layout.answering_dir == answering_dir()
    assert layout.logs_dir == logs_dir()
    assert layout.legacy_home == legacy_state_home()


def test_squadron_runs_dir_sits_under_the_user_home(user_home: Path) -> None:
    assert squadron_runs_dir() == user_home / ".config" / "squadron" / "runs"
