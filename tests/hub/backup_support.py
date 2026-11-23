"""A throwaway hub (store, certificate, key) for the backup tests (slice 260)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from amoeba.hub.backups import BackupSource
from amoeba.hub.certificate import make_certificate
from amoeba.store.store import Store

START = datetime(2026, 11, 21, 8, 0, tzinfo=UTC)


def at(minutes: int) -> datetime:
    return START + timedelta(minutes=minutes)


def make_hub_files(state: Path) -> BackupSource:
    """A migrated store holding one program row, and a certificate and key."""
    source = BackupSource(
        store_path=state / "amoeba.sqlite3",
        cert_path=state / "hub-cert.pem",
        key_path=state / "hub-key.pem",
    )
    make_certificate(source.cert_path, source.key_path)
    with Store.open(source.store_path) as store, store.write() as transaction:
        owner = transaction.execute("SELECT owner_id FROM owners").fetchone()[0]
        transaction.execute(
            "INSERT INTO programs (program_id, registered_at, updated_at, owner_id) "
            "VALUES ('demo', ?, ?, ?)",
            (START.isoformat(), START.isoformat(), owner),
        )
    return source
