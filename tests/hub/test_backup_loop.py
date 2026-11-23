"""The loop that takes a timed backup while the hub serves (slice 260, D14)."""

from __future__ import annotations

import logging
import stat
from datetime import UTC, datetime
from pathlib import Path

import anyio
import pytest

from amoeba.config.home import StateLayout
from amoeba.hub.backups import (
    BackupKind,
    BackupSource,
    newest_complete_backup,
    take_timed_backup_if_due,
)
from amoeba.hub.serve import BackupCheck, backup_loop
from hub.start_support import complete_state, hub_home

CHECK_SECONDS = 0.05
#: Small enough that a backup is due at every check.
DUE_EVERY_CHECK_HOURS = 1e-9
RUN_SECONDS = 0.6


def _check(layout: StateLayout, backup_dir: Path) -> BackupCheck:
    def run() -> Path | None:
        return take_timed_backup_if_due(
            backup_dir=backup_dir,
            source=BackupSource(layout.store_path, layout.hub_cert, layout.hub_key),
            keep=50,
            backup_hours=DUE_EVERY_CHECK_HOURS,
            now=datetime.now(UTC),
        )

    return run


async def _run_for(seconds: float, run_check: BackupCheck) -> None:
    with anyio.move_on_after(seconds):
        await backup_loop(CHECK_SECONDS, run_check)


def _timed(backup_dir: Path) -> int:
    kind_dir = backup_dir / BackupKind.TIMED.value
    return len(list(kind_dir.iterdir())) if kind_dir.exists() else 0


def test_the_loop_takes_a_timed_backup_without_a_restart(tmp_path: Path) -> None:
    layout, backup_dir = hub_home(tmp_path)
    complete_state(layout)

    anyio.run(_run_for, RUN_SECONDS, _check(layout, backup_dir))

    assert _timed(backup_dir) >= 2
    assert newest_complete_backup(backup_dir) is not None


def test_a_failed_check_is_logged_and_the_next_check_takes_the_backup(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    layout, backup_dir = hub_home(tmp_path)
    complete_state(layout)
    backup_dir.chmod(stat.S_IRUSR | stat.S_IXUSR)
    try:
        with caplog.at_level(logging.ERROR):
            anyio.run(_run_for, RUN_SECONDS, _check(layout, backup_dir))
    finally:
        backup_dir.chmod(stat.S_IRWXU)

    assert any("timed backup check failed" in r.getMessage() for r in caplog.records)
    assert _timed(backup_dir) == 0

    anyio.run(_run_for, RUN_SECONDS, _check(layout, backup_dir))

    assert _timed(backup_dir) >= 1


def test_a_store_that_went_missing_is_logged_and_the_loop_keeps_going(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    layout, backup_dir = hub_home(tmp_path)
    complete_state(layout)
    for suffix in ("", "-wal", "-shm"):
        Path(f"{layout.store_path}{suffix}").unlink(missing_ok=True)

    with caplog.at_level(logging.ERROR):
        anyio.run(_run_for, RUN_SECONDS, _check(layout, backup_dir))

    failures = [
        r for r in caplog.records if "timed backup check failed" in r.getMessage()
    ]
    assert len(failures) >= 2  # the loop went on after the first
    assert not layout.store_path.exists()
    assert _timed(backup_dir) == 0
