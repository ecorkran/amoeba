"""The shared ``--version`` label capture, driven by a fake ``sq`` on PATH."""

from __future__ import annotations

from pathlib import Path

import pytest

from amoeba.process.version_label import (
    SQ_EXECUTABLE,
    VERSION_UNAVAILABLE,
    capture_sq_version_label,
)

TIMEOUT_SECONDS = 5.0
SHORT_TIMEOUT_SECONDS = 0.2


@pytest.fixture
def fake_bin(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A directory that is the whole PATH, so only fakes placed there exist."""
    directory = tmp_path / "bin"
    directory.mkdir()
    monkeypatch.setenv("PATH", str(directory))
    return directory


def _fake_sq(directory: Path, body: str) -> None:
    script = directory / SQ_EXECUTABLE
    script.write_text(f"#!/bin/sh\n{body}\n")
    script.chmod(0o755)


def test_the_label_is_the_trimmed_stdout(fake_bin: Path) -> None:
    _fake_sq(fake_bin, 'echo "  squadron 0.21.9  "')
    assert capture_sq_version_label(TIMEOUT_SECONDS) == "squadron 0.21.9"


def test_a_missing_executable_is_unavailable(fake_bin: Path) -> None:
    assert capture_sq_version_label(TIMEOUT_SECONDS) == VERSION_UNAVAILABLE


def test_a_non_zero_exit_is_unavailable(fake_bin: Path) -> None:
    _fake_sq(fake_bin, "echo 0.21.9; exit 3")
    assert capture_sq_version_label(TIMEOUT_SECONDS) == VERSION_UNAVAILABLE


def test_a_timeout_is_unavailable(fake_bin: Path) -> None:
    _fake_sq(fake_bin, "exec /bin/sleep 5")
    assert capture_sq_version_label(SHORT_TIMEOUT_SECONDS) == VERSION_UNAVAILABLE
