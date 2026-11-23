"""A client home with a local store, and join lines, for the join tests (slice 260)."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

from store_open import open_local_store

from amoeba.config.home import StateLayout, state_layout
from amoeba.wire.fingerprint import fingerprint
from amoeba.wire.join_line import format_join_line
from hub.call_support import ALPHA_TOKEN
from hub.in_process_hub import InProcessHub

NOW = datetime(2026, 11, 21, 12, 0, tzinfo=UTC)


def line_for(hub: InProcessHub, token: str = ALPHA_TOKEN) -> str:
    """The join line `hub invite` would print for ``token``."""
    pem = hub.cert_path.read_text(encoding="utf-8")
    return format_join_line(hub.address, fingerprint(pem), token)


def client_layout() -> StateLayout:
    return state_layout()


def make_local_store(layout: StateLayout, *programs: str) -> Path:
    """A migrated local store holding these program ids."""
    with open_local_store(layout.store_path) as store, store.write() as transaction:
        for program in programs:
            transaction.execute(
                "INSERT INTO programs (program_id, registered_at, updated_at, "
                "owner_id) VALUES (?, ?, ?, ?)",
                (
                    program,
                    NOW.isoformat(),
                    NOW.isoformat(),
                    transaction.acting("programs").owner_id,
                ),
            )
    return layout.store_path


def program_ids(store_path: Path) -> list[str]:
    with closing(sqlite3.connect(store_path)) as connection:
        return sorted(
            r[0] for r in connection.execute("SELECT program_id FROM programs")
        )


def files_of(root: Path) -> list[str]:
    return sorted(str(p.relative_to(root)) for p in root.rglob("*"))
