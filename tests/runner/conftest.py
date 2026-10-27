"""Fixtures shared by the Runner tests."""

from __future__ import annotations

import pytest

from runner.tick_support import install_passing_gates


@pytest.fixture
def passing_checks(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pass every current step's pre-dispatch check (see ``PassingGates``)."""
    install_passing_gates(monkeypatch)
