"""The hub's life on real processes: restarts, restores, damage and migrations
(slice 260, D5, D14, D15)."""

from __future__ import annotations

import http.client
import json
import shutil
import sqlite3
import ssl
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

from hub_fixture import FIRST, SECOND, FixtureHub, two_machine_hub

from amoeba.hub.backups import BackupKind, BackupSource, take_backup
from hub.start_support import tree

TIMED = BackupKind.TIMED.value
PRE_MIGRATION = BackupKind.PRE_MIGRATION.value
NOW = datetime(2026, 11, 21, 12, 0, tzinfo=UTC)


def _timed(hub: FixtureHub) -> list[str]:
    directory = hub.backup_dir / TIMED
    return sorted(p.name for p in directory.iterdir()) if directory.exists() else []


def _decisions_work(hub: FixtureHub) -> None:
    for name in (FIRST, SECOND):
        done = hub.clients[name].run("decisions", "-j")
        assert done.code == 0, done.err


def _rows(hub: FixtureHub, query: str) -> list[tuple[object, ...]]:
    """Read the store on a plain connection, which never migrates it."""
    with closing(sqlite3.connect(hub.layout.store_path)) as connection:
        return [tuple(row) for row in connection.execute(query)]


def _no_local_machine(hub: FixtureHub) -> None:
    assert hub.process is None, "check a stopped hub's store"
    names = [row[0] for row in _rows(hub, "SELECT name FROM machines")]
    assert "local" not in names


def _backup(hub: FixtureHub) -> Path:
    done = hub.run_in(hub.home, "hub", "backup", "-j")
    assert done.code == 0, done.err
    return Path(json.loads(done.out)["path"])


def test_five_restarts_in_a_row_take_no_new_timed_backup(tmp_path: Path) -> None:
    with two_machine_hub(tmp_path) as hub:
        before = _timed(hub)
        assert len(before) == 1  # the first start's

        for _ in range(5):
            hub.restart()

        assert _timed(hub) == before
        _decisions_work(hub)
        hub.stop()
        _no_local_machine(hub)


def test_a_hub_started_from_a_backup_on_a_new_state_directory_serves_both_clients(
    tmp_path: Path,
) -> None:
    with two_machine_hub(tmp_path) as hub:
        backup = _backup(hub)
        hub.stop()
        hub.move_to_new_home("restored-hub-home")

        hub.start("--from-backup", str(backup))

        _decisions_work(hub)  # no new invite and no new join
        hub.stop()
        _no_local_machine(hub)


def test_keep_counts_hold_for_backups_and_the_log(tmp_path: Path) -> None:
    with two_machine_hub(
        tmp_path, backups_kept=2, hub_log_max_bytes=2000, hub_logs_kept=2
    ) as hub:
        for _ in range(6):
            _backup(hub)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_REQUIRED
        context.load_verify_locations(
            cafile=hub.clients[FIRST].home / "pinned-hub-cert.pem"
        )
        for number in range(150):
            connection = http.client.HTTPSConnection(
                "127.0.0.1", hub.port, context=context
            )
            connection.request(
                "POST", "/call/hello", body=b"{}", headers={"X": str(number)}
            )
            connection.getresponse().read()
            connection.close()

        assert len(_timed(hub)) == 2
        log_files = sorted(p.name for p in hub.layout.hub_log.parent.iterdir())
        assert len(log_files) == 2, log_files
        hub.stop()
        _no_local_machine(hub)


def test_a_missing_store_refuses_the_start_and_the_restore_serves_both_clients(
    tmp_path: Path,
) -> None:
    with two_machine_hub(tmp_path) as hub:
        backup = _backup(hub)
        hub.stop()
        for suffix in ("", "-wal", "-shm"):
            Path(f"{hub.layout.store_path}{suffix}").unlink(missing_ok=True)

        refused = hub.start_expecting_failure()

        assert refused.code == 3
        assert str(backup) in refused.err
        assert "--from-backup" in refused.err
        assert not hub.layout.store_path.exists()

        hub.start("--from-backup", str(backup))

        _decisions_work(hub)
        hub.stop()
        _no_local_machine(hub)


def test_a_store_removed_under_a_serving_hub_is_refused_and_never_replaced(
    tmp_path: Path,
) -> None:
    with two_machine_hub(tmp_path) as hub:
        timed_before = _timed(hub)
        for suffix in ("", "-wal", "-shm"):
            Path(f"{hub.layout.store_path}{suffix}").unlink(missing_ok=True)

        done = hub.clients[FIRST].run("decisions", "-j")
        backup = hub.run_in(hub.home, "hub", "backup", "-j")

        assert done.code == 3
        assert "hub_error" in done.err and "HubStoreMissingError" in done.err
        assert backup.code == 3 and "HubStoreMissingError" in backup.err
        assert not hub.layout.store_path.exists()
        assert _timed(hub) == timed_before
        assert hub.process is not None and hub.process.poll() is None


def test_a_new_certificate_locks_out_the_clients_until_they_join_again(
    tmp_path: Path,
) -> None:
    with two_machine_hub(tmp_path) as hub:
        hub.stop()
        hub.layout.hub_cert.unlink()
        shutil.rmtree(hub.backup_dir)
        hub.backup_dir.mkdir()

        hub.start()

        assert any("certificate is new" in line for line in hub.stderr_lines)
        for name in (FIRST, SECOND):
            done = hub.clients[name].run("decisions", "-j")
            assert done.code == 3 and "HubCertificateError" in done.err
        for name in (FIRST, SECOND):
            line = hub.invite(name)
            joined = hub.clients[name].run("join", line, "-j")
            assert joined.code == 0, joined.err
        _decisions_work(hub)
        hub.stop()
        _no_local_machine(hub)


def test_ten_backups_in_a_row_leave_no_partial_directory_and_the_rotation_holds(
    tmp_path: Path,
) -> None:
    with two_machine_hub(tmp_path, backups_kept=3, backup_hours=0.00001) as hub:
        for _ in range(10):
            _backup(hub)

        names = _timed(hub)
        assert len(names) == 3
        assert not [name for name in names if name.startswith(".partial-")]
        assert hub.process is not None and hub.process.poll() is None


def test_a_migration_that_fails_five_starts_in_a_row_keeps_one_backup_for_its_version(
    tmp_path: Path,
) -> None:
    with two_machine_hub(tmp_path) as hub:
        hub.stop()
        source = BackupSource(
            hub.layout.store_path, hub.layout.hub_cert, hub.layout.hub_key
        )
        for earlier in (8, 9):
            take_backup(
                BackupKind.PRE_MIGRATION,
                backup_dir=hub.backup_dir,
                source=source,
                keep=3,
                now=NOW.replace(minute=earlier),
                schema_version=earlier,
            )
        with closing(sqlite3.connect(hub.layout.store_path)) as connection:
            # Stamped below the schema, with the tables of the newest migration
            # already there: applying it fails on its first statement.
            connection.execute("UPDATE schema_meta SET version = 10")
            connection.commit()

        for _ in range(5):
            failed = hub.start_expecting_failure()
            assert failed.code == 3, failed.err

        names = sorted(p.name for p in (hub.backup_dir / PRE_MIGRATION).iterdir())
        assert len(names) == 3, names
        assert len([n for n in names if n.endswith("-v10")]) == 1
        assert any(n.endswith("-v8") for n in names)
        assert any(n.endswith("-v9") for n in names)
        _no_local_machine(hub)


def test_an_ordinary_command_in_the_hub_home_is_refused_and_changes_no_row(
    tmp_path: Path,
) -> None:
    with two_machine_hub(tmp_path) as hub:
        hub.stop()
        before = _counts(hub)

        done = hub.run_in(hub.home, "standing", "--text", "a ruling")

        assert done.code == 3
        assert "HubHomeError" in done.err
        assert _counts(hub) == before
        assert "local" not in [r[0] for r in _rows(hub, "SELECT name FROM machines")]
        assert tree(hub.home)  # the home is intact


TABLES = (
    "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
)


def _counts(hub: FixtureHub) -> dict[str, int]:
    names = [str(row[0]) for row in _rows(hub, TABLES)]
    return {
        name: int(str(_rows(hub, f"SELECT COUNT(*) FROM {name}")[0][0]))
        for name in names
    }
