"""Shared test fixtures.

Every fixture here creates its own throwaway store under pytest's ``tmp_path``
and destroys only what it created. No test touches the central per-supervisor
store path — that property is checked mechanically by the guard test in
``test_store_safety.py`` rather than assumed.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from inbox_harness import RealSubmission, damaged_variants, write_real_submission

from amoeba.store import Store


@pytest.fixture
def store_file(tmp_path: Path) -> Path:
    """Path to a throwaway store file that does not yet exist.

    Scope: function. Each test gets its own path under its own ``tmp_path``, so
    tests never share a store and never observe each other's writes.

    Safety: the path lies inside pytest's temporary directory, which pytest
    created and pytest removes. This fixture creates nothing and therefore
    destroys nothing — the file, if any, is created by the store under test,
    which is the only thing torn down with it.
    """
    return tmp_path / "throwaway.sqlite3"


@pytest.fixture
def store(store_file: Path) -> Iterator[Store]:
    """An open store backed by a throwaway file, closed when the test ends.

    Scope: function. The store is opened at :func:`store_file`, so it lives
    entirely inside pytest's temporary directory and no two tests share one.

    Safety: destroys only what it created. The fixture opens — and thereby
    creates — exactly one store file under ``tmp_path`` and closes it on
    teardown; removing the directory is pytest's own doing. It never resolves
    or opens the central per-supervisor store.
    """
    with Store.open(store_file) as opened:
        yield opened


@pytest.fixture
def supervisor_dir(tmp_path: Path) -> Path:
    """A throwaway supervisor directory: inbox, stores, lock, and PID file.

    Scope: function. Safety: it lies inside pytest's ``tmp_path``, is never the
    central directory, and this fixture creates nothing in it.
    """
    return tmp_path / "supervisor"


@pytest.fixture
def real_submission(supervisor_dir: Path) -> RealSubmission:
    """One file written by the real ``submit()`` into ``supervisor_dir``.

    Here, not in ``tests/inbox/conftest.py``: the tenant tests in
    ``tests/process/`` need it too, and conftest fixtures only apply downward.
    """
    return write_real_submission(supervisor_dir)


@pytest.fixture
def damaged_envelopes(real_submission: RealSubmission) -> dict[str, bytes]:
    """Truncated, wrong-version, and extra-fields copies of the real file."""
    return damaged_variants(real_submission)
