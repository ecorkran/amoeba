"""Hub backups: contents, rotation, partials and the lock (slice 260, D15)."""

from __future__ import annotations

import multiprocessing
import os
import signal
import sqlite3
import stat
import time
from contextlib import closing
from pathlib import Path

import pytest

from amoeba.hub.backups import (
    LOCK_FILE_NAME,
    PARTIAL_PREFIX,
    BackupError,
    BackupHooks,
    BackupKind,
    BackupSource,
    newest_complete_backup,
    take_backup,
    timed_backup_due,
)
from amoeba.store.errors import HubStoreMissingError
from amoeba.store.store import Store
from hub.backup_support import at, make_hub_files

KEEP = 3
FILES = {"amoeba.sqlite3", "hub-cert.pem", "hub-key.pem"}


@pytest.fixture
def source(tmp_path: Path) -> BackupSource:
    return make_hub_files(tmp_path / "state")


@pytest.fixture
def backup_dir(tmp_path: Path) -> Path:
    return tmp_path / "backups"


def _take(
    source: BackupSource,
    backup_dir: Path,
    minutes: int,
    kind: BackupKind = BackupKind.TIMED,
    schema_version: int | None = None,
    hooks: BackupHooks = BackupHooks(),  # noqa: B008
) -> Path:
    return take_backup(
        kind,
        backup_dir=backup_dir,
        source=source,
        keep=KEEP,
        now=at(minutes),
        schema_version=schema_version,
        hooks=hooks,
    )


def _dirs(backup_dir: Path, kind: BackupKind) -> list[str]:
    return sorted(p.name for p in (backup_dir / kind.value).iterdir())


def test_a_backup_holds_the_three_files_with_the_modes_and_the_same_rows(
    source: BackupSource, backup_dir: Path
) -> None:
    made = _take(source, backup_dir, 0)

    assert {p.name for p in made.iterdir()} == FILES
    assert stat.S_IMODE(made.stat().st_mode) == 0o700
    assert stat.S_IMODE(made.parent.stat().st_mode) == 0o700
    for name in FILES:
        assert stat.S_IMODE((made / name).stat().st_mode) == 0o600
    with closing(sqlite3.connect(made / "amoeba.sqlite3")) as copy:
        assert copy.execute("SELECT program_id FROM programs").fetchall() == [("demo",)]
    assert (made / "hub-key.pem").read_bytes() == source.key_path.read_bytes()


def test_a_pre_migration_name_carries_the_version(
    source: BackupSource, backup_dir: Path
) -> None:
    made = _take(source, backup_dir, 0, BackupKind.PRE_MIGRATION, schema_version=10)

    assert made.parent.name == "pre-migration"
    assert made.name.endswith("-v10")


def test_a_backup_is_due_when_none_exists_or_the_newest_is_old(
    source: BackupSource, backup_dir: Path
) -> None:
    assert timed_backup_due(backup_dir, at(0), 1) is True  # no directory yet
    _take(source, backup_dir, 0)

    assert timed_backup_due(backup_dir, at(59), 1) is False
    assert timed_backup_due(backup_dir, at(61), 1) is True


def test_a_pre_migration_backup_does_not_make_a_timed_one_not_due(
    source: BackupSource, backup_dir: Path
) -> None:
    _take(source, backup_dir, 0, BackupKind.PRE_MIGRATION, schema_version=10)

    assert timed_backup_due(backup_dir, at(1), 24) is True


def test_a_failure_partway_leaves_no_partial_directory_and_raises(
    source: BackupSource, backup_dir: Path
) -> None:
    def break_the_copy() -> None:
        raise sqlite3.OperationalError("disk full")

    with pytest.raises(BackupError, match="disk full"):
        _take(source, backup_dir, 0, hooks=BackupHooks(during_copy=break_the_copy))

    assert _dirs(backup_dir, BackupKind.TIMED) == []


def test_a_leftover_partial_is_gone_after_the_next_attempt_and_never_counts(
    source: BackupSource, backup_dir: Path
) -> None:
    leftover = backup_dir / "timed" / f"{PARTIAL_PREFIX}20260101T000000000000Z"
    leftover.mkdir(parents=True)
    (leftover / "amoeba.sqlite3").write_bytes(b"half")

    assert newest_complete_backup(backup_dir) is None
    made = _take(source, backup_dir, 0)

    assert _dirs(backup_dir, BackupKind.TIMED) == [made.name]


def test_each_kind_keeps_only_the_newest_kept(
    source: BackupSource, backup_dir: Path
) -> None:
    for minute in range(KEEP + 2):
        _take(source, backup_dir, minute)
        _take(source, backup_dir, minute, BackupKind.PRE_MIGRATION, minute)

    assert len(_dirs(backup_dir, BackupKind.TIMED)) == KEEP
    assert len(_dirs(backup_dir, BackupKind.PRE_MIGRATION)) == KEEP
    newest = newest_complete_backup(backup_dir)
    assert newest is not None
    assert newest.name.startswith(at(KEEP + 1).strftime("%Y%m%dT%H%M"))


def test_a_backup_succeeds_while_another_connection_holds_a_write_transaction(
    source: BackupSource, backup_dir: Path
) -> None:
    with Store.open(source.store_path) as holder, holder.write() as transaction:
        owner = transaction.execute("SELECT owner_id FROM owners").fetchone()[0]
        transaction.execute(
            "INSERT INTO programs (program_id, registered_at, updated_at, owner_id) "
            "VALUES ('uncommitted', 't', 't', ?)",
            (owner,),
        )
        made = _take(source, backup_dir, 0)

    with closing(sqlite3.connect(made / "amoeba.sqlite3")) as copy:
        rows = copy.execute("SELECT program_id FROM programs").fetchall()
    assert rows == [("demo",)]


def _slow_copy() -> None:
    time.sleep(0.6)


def _slow_backup(source: BackupSource, backup_dir: Path, minute: int) -> None:
    _take(source, backup_dir, minute, hooks=BackupHooks(during_copy=_slow_copy))


def test_two_backups_started_together_in_two_processes_both_complete(
    source: BackupSource, backup_dir: Path
) -> None:
    context = multiprocessing.get_context("fork")
    processes = [
        context.Process(target=_slow_backup, args=(source, backup_dir, minute))
        for minute in (0, 1)
    ]

    for process in processes:
        process.start()
    for process in processes:
        process.join(timeout=30)

    assert [process.exitcode for process in processes] == [0, 0]
    names = _dirs(backup_dir, BackupKind.TIMED)
    assert len(names) == 2
    assert not [name for name in names if name.startswith(PARTIAL_PREFIX)]
    for name in names:
        assert {p.name for p in (backup_dir / "timed" / name).iterdir()} == FILES


def _hold_the_lock_forever() -> None:
    time.sleep(60)


def _stuck_backup(source: BackupSource, backup_dir: Path) -> None:
    _take(source, backup_dir, 0, hooks=BackupHooks(during_copy=_hold_the_lock_forever))


def test_a_process_killed_while_holding_the_lock_does_not_stop_the_next_attempt(
    source: BackupSource, backup_dir: Path
) -> None:
    context = multiprocessing.get_context("fork")
    stuck = context.Process(target=_stuck_backup, args=(source, backup_dir))
    stuck.start()
    deadline = time.monotonic() + 10
    while not list((backup_dir / "timed").glob(f"{PARTIAL_PREFIX}*")):
        assert time.monotonic() < deadline, "the stuck backup never started"
        time.sleep(0.05)
    assert stuck.pid is not None
    os.kill(stuck.pid, signal.SIGKILL)
    stuck.join(timeout=10)

    made = _take(source, backup_dir, 5)

    assert _dirs(backup_dir, BackupKind.TIMED) == [made.name]
    assert (backup_dir / LOCK_FILE_NAME).exists()


def test_with_the_store_removed_a_backup_creates_nothing_and_keeps_the_rest(
    source: BackupSource, backup_dir: Path
) -> None:
    kept = [_take(source, backup_dir, minute) for minute in range(2)]
    source.store_path.unlink()
    for suffix in ("-wal", "-shm"):
        Path(f"{source.store_path}{suffix}").unlink(missing_ok=True)

    with pytest.raises(HubStoreMissingError):
        _take(source, backup_dir, 9)

    assert not source.store_path.exists()
    assert _dirs(backup_dir, BackupKind.TIMED) == [path.name for path in kept]


def test_five_pre_migration_backups_for_one_version_leave_one(
    source: BackupSource, backup_dir: Path
) -> None:
    _take(source, backup_dir, 0, BackupKind.PRE_MIGRATION, 8)
    _take(source, backup_dir, 1, BackupKind.PRE_MIGRATION, 9)
    made = [
        _take(source, backup_dir, minute, BackupKind.PRE_MIGRATION, 10)
        for minute in range(2, 7)
    ]
    last = made[-1]

    names = _dirs(backup_dir, BackupKind.PRE_MIGRATION)
    assert [n for n in names if n.endswith("-v10")] == [last.name]
    assert len(names) == 3
    assert any(n.endswith("-v8") for n in names)
    assert any(n.endswith("-v9") for n in names)


def test_a_missing_backup_dir_is_an_error_naming_it(tmp_path: Path) -> None:
    missing = tmp_path / "nowhere"

    with pytest.raises(BackupError, match="nowhere"):
        newest_complete_backup(missing)


def test_only_the_lock_file_and_a_partial_directory_is_no_backup(
    backup_dir: Path,
) -> None:
    (backup_dir / "timed" / f"{PARTIAL_PREFIX}20260101T000000000000Z").mkdir(
        parents=True
    )
    (backup_dir / LOCK_FILE_NAME).write_text("", encoding="utf-8")

    assert newest_complete_backup(backup_dir) is None
