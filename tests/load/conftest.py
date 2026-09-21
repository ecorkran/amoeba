"""Fixtures for the load tier.

Only the fixtures live here, because pytest's ``conftest`` name is reserved and
a test module cannot import from it unambiguously — the top-level
``tests/conftest.py`` shadows it. The tier's helpers are therefore in
``load_harness.py``, and the process harness itself is the shared
``tests/host_harness.py``, per the project's DRY rule.

Nothing here touches the real supervisor directory or the real Squadron runs
directory; every path is under pytest's ``tmp_path``.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# This tier is a package, so pytest inserts neither it nor its parent on
# sys.path. Both are added here: the parent for the shared ``host_harness``
# (kept in one place rather than copied into this tier), and this directory
# for the tier's own ``load_harness``.
for _directory in (Path(__file__).parent.parent, Path(__file__).parent):
    if str(_directory) not in sys.path:
        sys.path.insert(0, str(_directory))


@pytest.fixture
def supervisor_dir(tmp_path: Path) -> Path:
    """A throwaway supervisor directory. Never the real one."""
    directory = tmp_path / "supervisor"
    directory.mkdir()
    return directory


@pytest.fixture
def runs_dir(tmp_path: Path) -> Path:
    """A throwaway Squadron runs directory. Never the real one."""
    directory = tmp_path / "runs"
    directory.mkdir()
    return directory
