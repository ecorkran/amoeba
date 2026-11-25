"""Shared test setup: reap leaked test processes; keep every test off the real home."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from cf_fixtures import OUTSIDE_ANY_PROJECT, write_fake_cf_with_projects
from process_containment import reap_orphans

from amoeba.config import home as amoeba_homes

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


@pytest.fixture
def installed_build(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make this process resolve homes as the installed amoeba does.

    Tests run from the checkout's editable install, a development build, whose
    default homes are ``amoeba-dev``; a test of the installed defaults asks for this.
    """
    monkeypatch.setattr(amoeba_homes, "is_dev_build", lambda: False)


@pytest.fixture(autouse=True)
def fake_cf_on_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path_factory: pytest.TempPathFactory
) -> None:
    """Put a recorded ``cf`` first on ``PATH`` for every test.

    Context Forge is not installed on the CI machine, and commands that read the
    caller's project (``status``, ``changes``, naming at open) run ``cf``. This one
    answers from recordings, so no test depends on the machine's real ``cf``. A test
    that wants another ``cf``, or none, sets its own ``PATH``.
    """
    bin_dir = tmp_path_factory.mktemp("fake_cf_bin")
    write_fake_cf_with_projects(bin_dir, OUTSIDE_ANY_PROJECT)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")


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
