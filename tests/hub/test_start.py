"""The start sequence's steps 2 to 8, on real files (slice 260, D5, D14)."""

from __future__ import annotations

import logging
import socket
import sqlite3
import stat
from contextlib import closing
from pathlib import Path

import pytest

from amoeba.config.home import StateLayout
from amoeba.hub.backups import BackupKind, newest_complete_backup
from amoeba.hub.certificate import CertificateHooks, make_certificate
from amoeba.hub.errors import HubStartError
from amoeba.hub.hub_config import HubConfigError
from amoeba.hub.start import PreparedHub, StartHooks, prepare_start
from amoeba.hub.store_open import open_hub_store
from amoeba.store.migrations import EXPECTED_SCHEMA_VERSION
from hub.call_support import NOW
from hub.start_support import (
    backup_of,
    complete_state,
    hub_home,
    programs,
    tree,
    write_hub_yaml,
)

CERT = "hub-cert.pem"
KEY = "hub-key.pem"


class Stop(Exception):
    """A test's own stop, raised from a hook."""


@pytest.fixture
def home(tmp_path: Path) -> tuple[StateLayout, Path]:
    return hub_home(tmp_path)


def _no_log(_config: object) -> None:
    """Step 6 is the caller's; these tests leave no handler on the root logger."""


def _start(layout: StateLayout, hooks: StartHooks = StartHooks()) -> PreparedHub:  # noqa: B008
    return prepare_start(layout, now=NOW, start_log=_no_log, hooks=hooks)


def _started(layout: StateLayout) -> PreparedHub:
    prepared = _start(layout)
    prepared.listener.close()
    return prepared


def _stamp(layout: StateLayout, version: int) -> None:
    with closing(sqlite3.connect(layout.store_path)) as connection:
        connection.execute("UPDATE schema_meta SET version = ?", (version,))
        connection.commit()


def _version(layout: StateLayout) -> int:
    with closing(sqlite3.connect(layout.store_path)) as connection:
        return int(connection.execute("SELECT version FROM schema_meta").fetchone()[0])


def _damage(layout: StateLayout, remove: tuple[str, ...]) -> None:
    for name in remove:
        (layout.state_home / name).unlink()


LONE_OR_NONE = [(KEY,), (CERT,), (CERT, KEY)]


@pytest.mark.parametrize("remove", LONE_OR_NONE)
def test_a_store_with_a_lone_or_no_certificate_beside_a_backup_refuses(
    home: tuple[StateLayout, Path], remove: tuple[str, ...]
) -> None:
    layout, backup_dir = home
    complete_state(layout)
    backup = backup_of(layout, backup_dir)
    _damage(layout, remove)
    before = tree(layout.state_home)

    with pytest.raises(HubStartError) as raised:
        _start(layout)

    message = str(raised.value)
    assert all(name in message for name in remove)
    assert "--from-backup" in message
    assert "empty directory" in message
    assert str(backup) in message
    assert tree(layout.state_home) == before


@pytest.mark.parametrize("remove", LONE_OR_NONE)
def test_the_same_store_with_an_empty_backup_dir_starts_with_a_new_pair(
    home: tuple[StateLayout, Path],
    remove: tuple[str, ...],
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    layout, _backup_dir = home
    complete_state(layout)
    old_cert = layout.hub_cert.read_bytes()
    _damage(layout, remove)

    with caplog.at_level(logging.WARNING):
        prepared = _started(layout)

    assert programs(layout) == ["demo"]
    assert layout.hub_cert.exists() and layout.hub_key.exists()
    assert layout.hub_cert.read_bytes() != old_cert
    assert "certificate is new" in capsys.readouterr().err
    assert prepared.replaced is None
    assert any("certificate is new" in r.getMessage() for r in caplog.records)


def test_no_store_and_no_backup_with_a_full_pair_keeps_the_pair_and_makes_a_store(
    home: tuple[StateLayout, Path],
) -> None:
    layout, _ = home
    make_certificate(layout.hub_cert, layout.hub_key)
    cert, key = layout.hub_cert.read_bytes(), layout.hub_key.read_bytes()

    _started(layout)

    assert (layout.hub_cert.read_bytes(), layout.hub_key.read_bytes()) == (cert, key)
    assert layout.store_path.exists()


@pytest.mark.parametrize("lone", [CERT, KEY])
def test_a_lone_file_with_no_store_and_no_backup_is_replaced_by_a_new_pair(
    home: tuple[StateLayout, Path], lone: str
) -> None:
    layout, _ = home
    make_certificate(layout.hub_cert, layout.hub_key)
    other = KEY if lone == CERT else CERT
    (layout.state_home / other).unlink()
    old = (layout.state_home / lone).read_bytes()

    _started(layout)

    assert (layout.state_home / lone).read_bytes() != old
    assert layout.hub_cert.exists() and layout.hub_key.exists()
    assert layout.store_path.exists()


def test_a_state_directory_holding_only_logs_is_a_first_start(
    home: tuple[StateLayout, Path],
) -> None:
    layout, _ = home
    (layout.state_home / "logs" / "hub").mkdir(parents=True)

    _started(layout)

    assert layout.hub_cert.exists() and layout.store_path.exists()


def test_a_first_start_beside_a_stale_write_ahead_log_makes_a_clean_store(
    home: tuple[StateLayout, Path],
) -> None:
    # SQLite deletes a write-ahead log beside a zero-byte database when it opens one
    # (a new store is always that), so the start needs no code of its own for this.
    # This pins that reliance: if SQLite ever replayed the log, the row would appear.
    layout, _ = home
    complete_state(layout)
    wal = Path(f"{layout.store_path}-wal")
    store = open_hub_store(layout)  # held open, so the log still holds its rows
    with store.write() as transaction:
        owner = transaction.execute("SELECT owner_id FROM owners").fetchone()[0]
        transaction.execute(
            "INSERT INTO programs (program_id, registered_at, updated_at, owner_id) "
            "VALUES ('stale', 'x', 'x', ?)",
            (owner,),
        )
    stale_log = wal.read_bytes()
    store.close()
    for leftover in (layout.store_path, wal, Path(f"{layout.store_path}-shm")):
        leftover.unlink(missing_ok=True)
    wal.write_bytes(stale_log)

    _started(layout)

    assert programs(layout) == []
    assert not wal.exists() or wal.read_bytes() != stale_log


def test_a_first_start_stopped_after_the_key_is_finished_by_the_next(
    home: tuple[StateLayout, Path],
) -> None:
    layout, _ = home

    def stop() -> None:
        raise Stop

    with pytest.raises(Stop):
        _start(layout, StartHooks(certificate=CertificateHooks(after_key=stop)))
    assert layout.hub_key.exists() and not layout.hub_cert.exists()

    _started(layout)

    assert layout.hub_cert.exists() and layout.store_path.exists()


def test_a_first_start_stopped_before_the_store_is_finished_by_the_next(
    home: tuple[StateLayout, Path],
) -> None:
    layout, _ = home

    def stop() -> None:
        raise Stop

    with pytest.raises(Stop):
        _start(layout, StartHooks(before_store_step=stop))
    cert = layout.hub_cert.read_bytes()
    assert not layout.store_path.exists()

    _started(layout)

    assert layout.hub_cert.read_bytes() == cert
    assert layout.store_path.exists()


def test_a_missing_backup_dir_on_a_start_with_no_store_refuses_naming_it(
    tmp_path: Path,
) -> None:
    layout, backup_dir = hub_home(tmp_path)
    backup_dir.rmdir()

    with pytest.raises(HubStartError, match="backups"):
        _start(layout)

    assert not layout.store_path.exists()


def test_the_same_hub_yaml_beside_a_complete_state_starts(tmp_path: Path) -> None:
    layout, backup_dir = hub_home(tmp_path)
    complete_state(layout)
    backup_dir.rmdir()

    _started(layout)

    assert newest_complete_backup(backup_dir) is not None


def test_a_bad_hub_yaml_key_refuses_naming_it(
    home: tuple[StateLayout, Path],
) -> None:
    layout, backup_dir = home
    write_hub_yaml(layout, backup_dir)
    layout.hub_file.write_text(
        layout.hub_file.read_text(encoding="utf-8").replace(
            "backups_kept: 3", "backups_kept: 0"
        ),
        encoding="utf-8",
    )

    with pytest.raises(HubConfigError, match="backups_kept"):
        _start(layout)

    assert not layout.state_home.exists()


def test_a_schema_ten_store_with_an_unwritable_backup_dir_refuses_and_stays_at_ten(
    home: tuple[StateLayout, Path],
) -> None:
    layout, backup_dir = home
    complete_state(layout)
    _stamp(layout, EXPECTED_SCHEMA_VERSION - 1)
    backup_dir.chmod(stat.S_IRUSR | stat.S_IXUSR)
    try:
        with pytest.raises(HubStartError, match="not migrated"):
            _start(layout)
    finally:
        backup_dir.chmod(stat.S_IRWXU)

    assert _version(layout) == EXPECTED_SCHEMA_VERSION - 1


def test_a_taken_port_refuses_before_any_file_is_written(
    home: tuple[StateLayout, Path],
) -> None:
    layout, backup_dir = home
    complete_state(layout)
    _stamp(layout, EXPECTED_SCHEMA_VERSION - 1)
    taken = socket.socket()
    taken.bind(("127.0.0.1", 0))
    taken.listen()
    write_hub_yaml(layout, backup_dir, taken.getsockname()[1])
    before = tree(layout.state_home) + tree(backup_dir)

    try:
        with pytest.raises(HubStartError, match="cannot listen"):
            _start(layout)
    finally:
        taken.close()

    assert tree(layout.state_home) + tree(backup_dir) == before
    assert _version(layout) == EXPECTED_SCHEMA_VERSION - 1


@pytest.mark.parametrize("state", ["nothing", "pair", "lone_key"])
def test_no_store_beside_a_backup_refuses_names_it_and_makes_nothing(
    tmp_path: Path, state: str
) -> None:
    layout, backup_dir = hub_home(tmp_path)
    complete_state(layout)
    backup = backup_of(layout, backup_dir)
    for suffix in ("", "-wal", "-shm"):
        Path(f"{layout.store_path}{suffix}").unlink(missing_ok=True)
    if state == "nothing":
        _damage(layout, (CERT, KEY))
    elif state == "lone_key":
        _damage(layout, (CERT,))
    before = tree(layout.state_home)

    with pytest.raises(HubStartError) as raised:
        _start(layout)

    assert str(backup) in str(raised.value)
    assert "--from-backup" in str(raised.value)
    assert tree(layout.state_home) == before
    assert not layout.store_path.exists()


def test_the_same_no_store_start_with_an_empty_backup_dir_is_a_first_start(
    tmp_path: Path,
) -> None:
    layout, backup_dir = hub_home(tmp_path)
    complete_state(layout)
    backup_of(layout, backup_dir)
    for suffix in ("", "-wal", "-shm"):
        Path(f"{layout.store_path}{suffix}").unlink(missing_ok=True)
    elsewhere = tmp_path / "empty-backups"
    elsewhere.mkdir()
    write_hub_yaml(layout, elsewhere)

    _started(layout)

    assert layout.store_path.exists()
    assert programs(layout) == []


def test_an_unwritable_backup_dir_with_no_migration_due_starts_and_logs_the_failure(
    home: tuple[StateLayout, Path], caplog: pytest.LogCaptureFixture
) -> None:
    layout, backup_dir = home
    complete_state(layout)
    backup_dir.chmod(stat.S_IRUSR | stat.S_IXUSR)
    try:
        with caplog.at_level(logging.ERROR):
            _started(layout)
    finally:
        backup_dir.chmod(stat.S_IRWXU)

    assert any("timed backup" in record.getMessage() for record in caplog.records)
    assert newest_complete_backup(backup_dir) is None


def test_a_first_start_takes_a_timed_backup_and_five_restarts_take_no_more(
    home: tuple[StateLayout, Path],
) -> None:
    layout, backup_dir = home
    _started(layout)
    first = newest_complete_backup(backup_dir)

    for _ in range(5):
        _started(layout)

    assert first is not None
    assert sorted(p.name for p in (backup_dir / BackupKind.TIMED.value).iterdir()) == [
        first.name
    ]
