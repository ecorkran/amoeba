"""Shared test setup: reap test processes an earlier, killed session left running."""

from __future__ import annotations

import sys

import pytest
from process_containment import reap_orphans


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
