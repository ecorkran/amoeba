"""``report_release`` never runs ``cf`` while it holds the write lock (slice 227, D2).

The timing in ``test_report_release_load`` cannot see a ``cf`` call that moved inside
the transaction: a fake ``cf`` returns at once. So the fake ``cf`` here asks the
database, from a second connection with no wait, whether anyone holds the write lock
at the moment it is called.
"""

from __future__ import annotations

import sqlite3
import subprocess
from collections.abc import Sequence
from contextlib import closing
from dataclasses import dataclass, field
from pathlib import Path

from operations.release_support import (
    PROVIDER_DIR,
    SettableClock,
    release_cf,
    release_deps,
)
from store.release_support import FULL_HASH, seed_members

from amoeba.operations.report_release import report_release
from amoeba.operations.report_release_models import ReportOutcome
from amoeba.store.store import Store


def write_lock_is_held(database: Path) -> bool:
    """True when another connection cannot take the write lock right now."""
    with closing(sqlite3.connect(database, timeout=0, isolation_level=None)) as probe:
        try:
            probe.execute("BEGIN IMMEDIATE")
        except sqlite3.OperationalError:
            return True
        probe.execute("ROLLBACK")
        return False


@dataclass
class LockProbingCf:
    """The release ``cf`` double, recording whether the write lock was held at each
    call."""

    database: Path
    lock_held_at_call: list[bool] = field(default_factory=lambda: [])

    def __call__(
        self, argv: Sequence[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        self.lock_held_at_call.append(write_lock_is_held(self.database))
        return release_cf()(argv, **kwargs)


def test_the_probe_sees_a_held_write_lock(tmp_path: Path) -> None:
    with Store.open(tmp_path / "amoeba.sqlite3") as store:
        assert not write_lock_is_held(store.path)
        with store.write():
            assert write_lock_is_held(store.path)


def test_report_release_resolves_the_member_without_holding_the_write_lock(
    tmp_path: Path,
) -> None:
    with Store.open(tmp_path / "amoeba.sqlite3") as store:
        seed_members(store)
        cf = LockProbingCf(store.path)
        deps = release_deps(tmp_path, SettableClock(), cf=cf)

        result = report_release(
            store,
            {"commit": FULL_HASH, "changed": "a change", "touched": ["api"]},
            directory=PROVIDER_DIR,
            deps=deps,
        )

    assert result.outcome == ReportOutcome.RECORDED
    assert cf.lock_held_at_call, "the member is resolved through cf"
    assert not any(cf.lock_held_at_call)
