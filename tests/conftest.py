"""Shared test setup: reap leaked test processes; keep every test off the real home."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from process_containment import reap_orphans

#: The one variable the code reads to locate the store and config (slice 222, D1).
AMOEBA_HOME_VARIABLE = "AMOEBA_HOME"


@pytest.fixture(autouse=True)
def amoeba_home(
    monkeypatch: pytest.MonkeyPatch, tmp_path_factory: pytest.TempPathFactory
) -> Path:
    """Point ``AMOEBA_HOME`` at a fresh directory for every test (D10).

    Nothing a test opens can resolve to the real ``~/.config/amoeba``.
    Subprocesses inherit it. monkeypatch restores the variable afterwards.
    """
    home = tmp_path_factory.mktemp("amoeba_home")
    monkeypatch.setenv(AMOEBA_HOME_VARIABLE, str(home))
    return home


def pytest_sessionstart(session: pytest.Session) -> None:
    """Kill test processes an earlier, killed session left running.

    Teardown fixtures do not run when pytest is killed, so its children keep
    going. See ``process_containment``. Skipped on a worker of a parallel run,
    which would otherwise race its siblings' children.
    """
    if hasattr(session.config, "workerinput"):
        return
    reaped = reap_orphans()
    if reaped:
        sys.stderr.write(
            f"reaped leaked test processes from an earlier run: {list(reaped)}\n"
        )
