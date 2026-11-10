"""The autouse fixture gives each test its own throwaway ``AMOEBA_HOME``."""

from __future__ import annotations

import os
from pathlib import Path

_seen: list[str] = []


def _record(amoeba_home: Path) -> None:
    value = os.environ["AMOEBA_HOME"]
    assert value == str(amoeba_home)
    assert Path(value) != Path.home() / ".config" / "amoeba"
    _seen.append(value)


def test_first_test_sees_its_own_home(amoeba_home: Path) -> None:
    _record(amoeba_home)


def test_second_test_sees_a_different_home(amoeba_home: Path) -> None:
    _record(amoeba_home)
    assert len(set(_seen)) == len(_seen)
