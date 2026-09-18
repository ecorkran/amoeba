"""Tests for central store path resolution.

Assertions are made against the named constants in ``paths``, never against a
hardcoded ``~/.config/amoeba`` literal — the point of the constants is that the
convention is defined exactly once.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from amoeba.store.paths import (
    DEFAULT_STORE_DIR,
    STORE_DIR_ENV_VAR,
    STORE_DIR_NAME,
    STORE_FILE_SUFFIX,
    XDG_CONFIG_HOME_ENV_VAR,
    store_dir,
    store_path,
)


def test_override_takes_precedence_over_xdg(tmp_path: Path) -> None:
    """The explicit override wins even when XDG is also set."""
    override = tmp_path / "override"
    xdg = tmp_path / "xdg"
    env = {
        STORE_DIR_ENV_VAR: str(override),
        XDG_CONFIG_HOME_ENV_VAR: str(xdg),
    }

    assert store_dir(env) == override


def test_xdg_takes_precedence_over_default(tmp_path: Path) -> None:
    """With the override unset, XDG determines the directory."""
    xdg = tmp_path / "xdg"
    env = {XDG_CONFIG_HOME_ENV_VAR: str(xdg)}

    assert store_dir(env) == xdg / STORE_DIR_NAME


def test_default_when_neither_is_set() -> None:
    """With neither variable set, the named default constant is used."""
    assert store_dir({}) == DEFAULT_STORE_DIR


def test_empty_override_falls_through_to_xdg(tmp_path: Path) -> None:
    """An empty override is not an override — it is an unset variable."""
    xdg = tmp_path / "xdg"
    env = {STORE_DIR_ENV_VAR: "", XDG_CONFIG_HOME_ENV_VAR: str(xdg)}

    assert store_dir(env) == xdg / STORE_DIR_NAME


def test_store_path_is_project_keyed(tmp_path: Path) -> None:
    """Two project ids resolve to two different files in the same directory."""
    env = {STORE_DIR_ENV_VAR: str(tmp_path)}

    first = store_path("alpha", env)
    second = store_path("beta", env)

    assert first != second
    assert first.parent == second.parent == tmp_path
    assert first.name == f"alpha{STORE_FILE_SUFFIX}"


def test_store_path_reads_process_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """With no explicit mapping, resolution reads the process environment."""
    monkeypatch.setenv(STORE_DIR_ENV_VAR, "/tmp/amoeba-env-test")

    assert store_path("demo").parent == Path("/tmp/amoeba-env-test")


@pytest.mark.parametrize("project_id", ["", "a/b", ".", ".."])
def test_store_path_rejects_unusable_project_ids(project_id: str) -> None:
    """A project id that could escape the store directory raises."""
    with pytest.raises(ValueError):
        store_path(project_id, {STORE_DIR_ENV_VAR: "/tmp/amoeba-reject-test"})


def test_resolution_creates_nothing(tmp_path: Path) -> None:
    """Resolution is pure: no directory and no file is created by calling it."""
    root = tmp_path / "never-created"
    env = {STORE_DIR_ENV_VAR: str(root)}

    resolved_dir = store_dir(env)
    resolved_file = store_path("demo", env)

    assert not resolved_dir.exists()
    assert not resolved_file.exists()
    assert list(tmp_path.iterdir()) == []
