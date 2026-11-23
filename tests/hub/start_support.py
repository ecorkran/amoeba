"""A hub home for the start and restore tests (slice 260)."""

from __future__ import annotations

import socket
from contextlib import closing
from pathlib import Path

import yaml

from amoeba.config.home import StateLayout
from amoeba.hub.backups import BackupKind, BackupSource, take_backup
from amoeba.hub.certificate import make_certificate
from amoeba.hub.store_open import open_hub_store
from hub.call_support import NOW, layout_in

BACKUPS_KEPT = 3


def free_port() -> int:
    with closing(socket.socket()) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def write_hub_yaml(
    layout: StateLayout, backup_dir: Path, port: int | None = None
) -> int:
    """``hub.yaml`` on loopback with a free port; returns the port."""
    chosen = free_port() if port is None else port
    layout.hub_file.parent.mkdir(parents=True, exist_ok=True)
    layout.hub_file.write_text(
        yaml.safe_dump(
            {
                "bind": "127.0.0.1",
                "port": chosen,
                "address": f"127.0.0.1:{chosen}",
                "backup_dir": str(backup_dir),
                "backup_hours": 24,
                "backups_kept": BACKUPS_KEPT,
                "hub_log_max_bytes": 100000,
                "hub_logs_kept": 3,
            }
        ),
        encoding="utf-8",
    )
    return chosen


def hub_home(root: Path) -> tuple[StateLayout, Path]:
    """A layout, its backup directory (empty, existing) and a ``hub.yaml``."""
    layout = layout_in(root)
    backup_dir = root / "backups"
    backup_dir.mkdir()
    write_hub_yaml(layout, backup_dir)
    return layout, backup_dir


def complete_state(layout: StateLayout) -> None:
    """A store with one program row, and a certificate and key."""
    make_certificate(layout.hub_cert, layout.hub_key)
    with open_hub_store(layout, create=True) as store:
        with store.write() as transaction:
            owner = transaction.execute("SELECT owner_id FROM owners").fetchone()[0]
            transaction.execute(
                "INSERT INTO programs (program_id, registered_at, updated_at, "
                "owner_id) VALUES ('demo', ?, ?, ?)",
                (NOW.isoformat(), NOW.isoformat(), owner),
            )


def backup_of(layout: StateLayout, backup_dir: Path) -> Path:
    """A timed backup of the current state."""
    return take_backup(
        BackupKind.TIMED,
        backup_dir=backup_dir,
        source=BackupSource(layout.store_path, layout.hub_cert, layout.hub_key),
        keep=BACKUPS_KEPT,
        now=NOW,
    )


def tree(root: Path) -> list[str]:
    return sorted(str(path.relative_to(root)) for path in root.rglob("*"))


def programs(layout: StateLayout) -> list[str]:
    with open_hub_store(layout) as store, store.read() as transaction:
        return [
            row[0] for row in transaction.execute("SELECT program_id FROM programs")
        ]
