"""Schema version detection and the numbered-migration runner.

At open, the stamp in ``schema_meta`` is read before anything else and compared
against :data:`EXPECTED_SCHEMA_VERSION`. Missing or lower means the numbered
``.sql`` files above it are applied in order inside a transaction. Higher means
the store was written by newer code, which raises rather than silently
downgrading — the store holds lifecycle history that cannot be reconstructed.

The ``.sql`` files deliberately omit ``IF NOT EXISTS``. The version gate is the
protection against re-application; idempotent DDL would mask a genuine
double-apply bug instead of failing on it.
"""

from __future__ import annotations

import logging
import re
import sqlite3
from importlib import resources
from importlib.resources.abc import Traversable
from typing import Final

from amoeba.store import sql
from amoeba.store.models import StoreCorruptError, StoreSchemaError

logger = logging.getLogger(__name__)

#: Package holding the numbered ``.sql`` files. Read through ``importlib
#: .resources`` so migrations resolve from an installed wheel, not only from a
#: source checkout. Named ``schema`` rather than ``migrations`` because this
#: module already owns that name — a sibling directory of the same name is
#: shadowed by this module and its resources become unreachable.
MIGRATIONS_PACKAGE: Final = "amoeba.store.schema"

#: The schema version this code expects. Bumped with each migration added.
EXPECTED_SCHEMA_VERSION: Final = 3

#: Version stamped on a store whose ``schema_meta`` table does not exist yet.
UNINITIALIZED_SCHEMA_VERSION: Final = 0

#: Numbered migration filename: three digits, an underscore, a label.
MIGRATION_FILENAME_PATTERN: Final = re.compile(r"^(\d{3})_[a-z0-9_]+\.sql$")


def _migration_files() -> list[tuple[int, Traversable]]:
    """Return every migration as ``(version, resource)``, ordered by version.

    Raises:
        StoreSchemaError: If two migrations claim the same version, which would
            make the applied order ambiguous.
    """
    found: dict[int, Traversable] = {}

    for entry in resources.files(MIGRATIONS_PACKAGE).iterdir():
        match = MIGRATION_FILENAME_PATTERN.match(entry.name)
        if match is None:
            continue

        version = int(match.group(1))
        if version in found:
            raise StoreSchemaError(
                f"duplicate migration version {version}: "
                f"{found[version].name} and {entry.name}"
            )
        found[version] = entry

    return sorted(found.items())


def read_schema_version(connection: sqlite3.Connection) -> int:
    """Read the stamp, or :data:`UNINITIALIZED_SCHEMA_VERSION` if unstamped.

    Args:
        connection: An open connection to the store.

    Returns:
        The stamped version, or ``0`` for a store with no ``schema_meta`` table.

    Raises:
        StoreCorruptError: If the file is not a readable SQLite database, or
            carries a ``schema_meta`` table that cannot be read. Such a store is
            never re-created or treated as fresh.
    """
    try:
        table_row = connection.execute(
            sql.SELECT_TABLE_EXISTS, (sql.TABLE_SCHEMA_META,)
        ).fetchone()
        if table_row is None:
            return UNINITIALIZED_SCHEMA_VERSION

        version_row = connection.execute(
            sql.SELECT_SCHEMA_VERSION, (sql.SCHEMA_META_ROW_ID,)
        ).fetchone()
    except sqlite3.DatabaseError as error:
        # Specific: a malformed or non-SQLite file surfaces here. Re-raised as a
        # typed store error so no caller mistakes it for an empty store.
        logger.exception("cannot read schema version")
        raise StoreCorruptError(f"cannot read schema version: {error}") from error

    if version_row is None:
        raise StoreCorruptError(
            f"{sql.TABLE_SCHEMA_META} exists but holds no version row"
        )

    version = version_row[0]
    if not isinstance(version, int):
        raise StoreCorruptError(f"schema version is not an integer: {version!r}")

    return version


def _apply_migration(
    connection: sqlite3.Connection, version: int, resource: Traversable
) -> None:
    """Apply one migration and advance the stamp, inside one transaction."""
    script = resource.read_text(encoding="utf-8")

    with connection:
        connection.executescript(script)
        connection.execute(sql.UPSERT_SCHEMA_VERSION, (sql.SCHEMA_META_ROW_ID, version))


def migrate(
    connection: sqlite3.Connection, expected_version: int = EXPECTED_SCHEMA_VERSION
) -> int:
    """Bring the store up to ``expected_version``, applying migrations in order.

    Args:
        connection: An open connection to the store.
        expected_version: The version to migrate to. Defaults to the version
            this code expects; parameterized so tests can stage an older store.

    Returns:
        The version stamped when this returns.

    Raises:
        StoreSchemaError: If the store is stamped newer than ``expected_version``
            — never a silent downgrade — or if a needed migration is missing.
        StoreCorruptError: If the existing stamp cannot be read.
    """
    current = read_schema_version(connection)

    if current > expected_version:
        raise StoreSchemaError(
            f"store schema version {current} is newer than the expected "
            f"version {expected_version}; refusing to downgrade"
        )

    if current == expected_version:
        return current

    pending = [
        (version, resource)
        for version, resource in _migration_files()
        if current < version <= expected_version
    ]

    expected_versions = list(range(current + 1, expected_version + 1))
    if [version for version, _ in pending] != expected_versions:
        raise StoreSchemaError(
            f"missing migrations between version {current} and {expected_version}; "
            f"found {[version for version, _ in pending]}"
        )

    for version, resource in pending:
        # executescript commits any open transaction, so each migration is its
        # own unit: a failure leaves the stamp at the last version that applied.
        _apply_migration(connection, version, resource)

    return expected_version
