"""Numbered migrations, ``store/schema/NNN_label.sql``, applied in order (D4).

``migrate`` runs in one immediate transaction, so two processes opening a new store
serialize on the lock and the second applies nothing. A store stamped higher than
this code expects is refused and left untouched. A sqlite3 failure propagates raw;
``Store.open`` maps it to a typed error.

Statements are run one at a time (``executescript`` would commit the transaction
first). Files omit ``IF NOT EXISTS``: the version stamp is what prevents
re-application, and idempotent DDL would hide a double-apply bug.
"""

from __future__ import annotations

import re
import sqlite3
from importlib import resources
from typing import Final

from amoeba.store import sql
from amoeba.store.errors import StoreCorruptError, StoreSchemaError

#: The highest numbered file in ``store/schema/``. Bumped with each migration added;
#: ``tests/store/test_migrations.py`` pins it to the files.
EXPECTED_SCHEMA_VERSION: Final = 3

#: Stamp of a store with no ``schema_meta`` table yet, as a new store has.
UNINITIALIZED_SCHEMA_VERSION: Final = 0

#: Read through ``importlib.resources`` so migrations resolve from an installed wheel.
SCHEMA_DIRECTORY: Final = "schema"

#: Three digits, an underscore, a label.
MIGRATION_FILENAME_PATTERN: Final = re.compile(r"^(\d{3})_[a-z0-9_]+\.sql$")

COMMENT_LINE_PREFIX: Final = "--"


def migration_files() -> list[tuple[int, str]]:
    """Every migration as ``(version, file text)``, in order.

    Raises:
        StoreSchemaError: Versions are duplicated or do not run 1, 2, 3, ...
    """
    found: dict[int, str] = {}
    for entry in (resources.files("amoeba.store") / SCHEMA_DIRECTORY).iterdir():
        match = MIGRATION_FILENAME_PATTERN.match(entry.name)
        if match is None:
            continue
        version = int(match.group(1))
        if version in found:
            raise StoreSchemaError(f"duplicate migration version {version}")
        found[version] = entry.read_text(encoding="utf-8")
    if sorted(found) != list(range(1, len(found) + 1)):
        raise StoreSchemaError(
            f"migration versions are not contiguous: {sorted(found)}"
        )
    return sorted(found.items())


def split_statements(script: str) -> list[str]:
    """The complete SQL statements of ``script``, each with its leading comments."""
    statements: list[str] = []
    buffer = ""
    for line in script.splitlines(keepends=True):
        buffer += line
        if sqlite3.complete_statement(buffer):
            statements.append(buffer.strip())
            buffer = ""
    leftover = [
        line
        for line in buffer.splitlines()
        if line.strip() and not line.strip().startswith(COMMENT_LINE_PREFIX)
    ]
    if leftover:
        raise StoreSchemaError(f"migration ends in an incomplete statement: {leftover}")
    return statements


def read_schema_version(connection: sqlite3.Connection) -> int:
    """The stamped version; ``UNINITIALIZED_SCHEMA_VERSION`` when unstamped."""
    if (
        connection.execute(sql.SELECT_TABLE_EXISTS, (sql.TABLE_SCHEMA_META,)).fetchone()
        is None
    ):
        return UNINITIALIZED_SCHEMA_VERSION
    row = connection.execute(
        sql.SELECT_SCHEMA_VERSION, (sql.SCHEMA_META_ROW_ID,)
    ).fetchone()
    if row is None or not isinstance(row[0], int):
        raise StoreCorruptError("schema_meta holds no integer version")
    return row[0]


def _apply_pending(connection: sqlite3.Connection) -> bool:
    """Apply every migration above the stamp; ``True`` when any was applied.

    Raises:
        StoreSchemaError: The store is stamped higher than this code expects.
    """
    current = read_schema_version(connection)
    if current > EXPECTED_SCHEMA_VERSION:
        raise StoreSchemaError(
            f"store is at schema version {current}, newer than the "
            f"{EXPECTED_SCHEMA_VERSION} this code expects; refusing to downgrade"
        )
    applied = False
    for version, script in migration_files():
        if version <= current:
            continue
        for statement in split_statements(script):
            connection.execute(statement)
        connection.execute(sql.UPSERT_SCHEMA_VERSION, (sql.SCHEMA_META_ROW_ID, version))
        applied = True
    return applied


def migrate(connection: sqlite3.Connection) -> int:
    """Bring the store to ``EXPECTED_SCHEMA_VERSION``; returns the stamped version.

    The connection must be in autocommit mode (``isolation_level=None``). Foreign
    keys are off for the transaction (the pragma does nothing inside one), so a
    migration may rebuild a referenced table; before commit ``foreign_key_check``
    must find nothing. They are on again afterward, committed or not.

    Raises:
        StoreSchemaError: The store is stamped higher than this code expects.
        StoreCorruptError: A migration left a dangling foreign key; rolled back.
    """
    connection.execute(sql.PRAGMA_FOREIGN_KEYS_OFF)
    try:
        connection.execute(sql.BEGIN_IMMEDIATE)
        try:
            if _apply_pending(connection):
                violations = connection.execute(sql.PRAGMA_FOREIGN_KEY_CHECK).fetchall()
                if violations:
                    raise StoreCorruptError(
                        f"migration left {len(violations)} dangling foreign "
                        f"key(s), first: {tuple(violations[0])}"
                    )
            connection.execute(sql.COMMIT)
        except BaseException:
            if connection.in_transaction:
                connection.execute(sql.ROLLBACK)
            raise
    finally:
        connection.execute(sql.PRAGMA_FOREIGN_KEYS_ON)
    return EXPECTED_SCHEMA_VERSION
