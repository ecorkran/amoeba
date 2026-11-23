"""Hub backups: timed, and before a migration (slice 260, D15).

A backup is a directory holding the store (made with SQLite's backup call on its own
read-only connection), ``hub-cert.pem`` and ``hub-key.pem``, with modes ``0700`` and
``0600`` because it holds the key and the token hashes. Each is written under a
``.partial-`` name and renamed when complete, so a crash mid-copy never counts as the
newest. One attempt at a time holds an exclusive file lock on ``<backup_dir>/.lock``,
from before it deletes a partial directory until after it rotates.
"""

from __future__ import annotations

import fcntl
import re
import shutil
import sqlite3
from collections.abc import Callable, Generator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Final

from amoeba.config.home import HUB_CERT_FILE_NAME, HUB_KEY_FILE_NAME, STORE_FILE_NAME
from amoeba.store.errors import HubStoreMissingError
from amoeba.store.relocate import backup_store

#: How often a serving hub checks whether a timed backup is due.
BACKUP_CHECK_SECONDS: Final = 300
#: The lock file: one empty file in ``backup_dir``, kept; its lock ends with its holder.
LOCK_FILE_NAME: Final = ".lock"
PARTIAL_PREFIX: Final = ".partial-"
#: ``<UTC stamp>``: sorts by time; microseconds so two backups in a second differ.
STAMP_FORMAT: Final = "%Y%m%dT%H%M%S%fZ"
DIRECTORY_MODE: Final = 0o700
FILE_MODE: Final = 0o600
_STAMP: Final = re.compile(r"^(\d{8}T\d{12}Z)")
_VERSION_SUFFIX: Final = re.compile(r"-v(\d+)$")


class BackupKind(StrEnum):
    """The two rotations; each is a directory under ``backup_dir`` named by it."""

    TIMED = "timed"
    PRE_MIGRATION = "pre-migration"


class BackupError(Exception):
    """A backup could not be taken or read; names the path and the cause."""


@dataclass(frozen=True)
class BackupHooks:
    """The fault seam of the copy: called once the partial directory exists and
    before the store is copied. Production passes none."""

    during_copy: Callable[[], None] | None = None


@dataclass(frozen=True)
class BackupSource:
    """What a backup copies."""

    store_path: Path
    cert_path: Path
    key_path: Path


def _is_partial(path: Path) -> bool:
    return path.name.startswith(PARTIAL_PREFIX)


def _complete_in(kind_dir: Path) -> list[Path]:
    """The complete backup directories of one kind, oldest first."""
    if not kind_dir.is_dir():
        return []
    found = [
        path
        for path in kind_dir.iterdir()
        if path.is_dir() and not _is_partial(path) and _STAMP.match(path.name)
    ]
    return sorted(found, key=lambda path: path.name)


def _stamp_time(path: Path) -> datetime:
    match = _STAMP.match(path.name)
    if match is None:
        raise BackupError(f"{path} is not a backup directory name")
    return datetime.strptime(match.group(1), STAMP_FORMAT).replace(tzinfo=UTC)


def _list(directory: Path) -> list[Path]:
    try:
        return [
            entry
            for kind in BackupKind
            for entry in _complete_in(directory / kind.value)
        ]
    except OSError as error:
        raise BackupError(
            f"cannot read the backup directory {directory}: {error}"
        ) from error


def newest_complete_backup(backup_dir: Path) -> Path | None:
    """The newest complete backup of either kind, or ``None`` when there is none.

    A ``.partial-`` directory and the lock file are not backups.

    Raises:
        BackupError: ``backup_dir`` does not exist or cannot be listed.
    """
    if not backup_dir.is_dir():
        raise BackupError(f"the backup directory {backup_dir} does not exist")
    found = _list(backup_dir)
    return max(found, key=_stamp_time, default=None)


def timed_backup_due(backup_dir: Path, now: datetime, backup_hours: float) -> bool:
    """Whether a timed backup is due: there is none, or the newest is older than
    ``backup_hours``. A ``backup_dir`` that does not exist yet holds none.

    Raises:
        BackupError: ``backup_dir`` exists but cannot be read.
    """
    if not backup_dir.exists():
        return True
    try:
        timed = _complete_in(backup_dir / BackupKind.TIMED.value)
    except OSError as error:
        raise BackupError(
            f"cannot read the backup directory {backup_dir}: {error}"
        ) from error
    if not timed:
        return True
    return now - _stamp_time(timed[-1]) > timedelta(hours=backup_hours)


@contextmanager
def _exclusive_lock(backup_dir: Path) -> Generator[None]:
    """Wait for the backup lock; the operating system frees it when its holder exits."""
    backup_dir.mkdir(parents=True, exist_ok=True)
    with (backup_dir / LOCK_FILE_NAME).open("a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def _write_backup(partial: Path, source: BackupSource, hooks: BackupHooks) -> None:
    partial.mkdir(mode=DIRECTORY_MODE)
    partial.chmod(DIRECTORY_MODE)
    if hooks.during_copy is not None:
        hooks.during_copy()
    backup_store(source.store_path, partial / STORE_FILE_NAME)
    shutil.copyfile(source.cert_path, partial / HUB_CERT_FILE_NAME)
    shutil.copyfile(source.key_path, partial / HUB_KEY_FILE_NAME)
    for name in (STORE_FILE_NAME, HUB_CERT_FILE_NAME, HUB_KEY_FILE_NAME):
        (partial / name).chmod(FILE_MODE)


def _final_name(kind: BackupKind, now: datetime, schema_version: int | None) -> str:
    stamp = now.astimezone(UTC).strftime(STAMP_FORMAT)
    if kind is BackupKind.PRE_MIGRATION:
        if schema_version is None:
            raise ValueError("a pre-migration backup needs the schema version")
        return f"{stamp}-v{schema_version}"
    return stamp


def _delete_partials(kind_dir: Path) -> None:
    for entry in kind_dir.iterdir():
        if _is_partial(entry):
            shutil.rmtree(entry, ignore_errors=True)


def _replace_same_version(kind_dir: Path, final: Path) -> None:
    """After a complete pre-migration backup, delete the other ones for its version."""
    version = _VERSION_SUFFIX.search(final.name)
    if version is None:
        return
    for other in _complete_in(kind_dir):
        match = _VERSION_SUFFIX.search(other.name)
        if other != final and match is not None and match.group(1) == version.group(1):
            shutil.rmtree(other)


def _rotate(kind_dir: Path, keep: int) -> None:
    for old in _complete_in(kind_dir)[:-keep]:
        shutil.rmtree(old)


def take_backup(  # noqa: PLR0913 - the kind, where, what, how many and when
    kind: BackupKind,
    *,
    backup_dir: Path,
    source: BackupSource,
    keep: int,
    now: datetime,
    schema_version: int | None = None,
    hooks: BackupHooks = BackupHooks(),  # noqa: B008  frozen, no state to share
) -> Path:
    """Take one backup of ``kind`` and return its directory.

    Holds the backup lock for the whole attempt. A failure deletes this attempt's
    partial directory and raises; a leftover partial directory of an earlier crash is
    deleted first. Rotation to ``keep`` and, for a pre-migration backup, the removal of
    older ones for the same schema version follow a complete backup.

    Raises:
        HubStoreMissingError: No store at ``source.store_path``; nothing was made.
        BackupError: Anything else; names the path and the cause.
    """
    if not source.store_path.exists():
        raise HubStoreMissingError(
            f"the hub has no store at {source.store_path} to back up"
        )
    kind_dir = backup_dir / kind.value
    final = kind_dir / _final_name(kind, now, schema_version)
    partial = kind_dir / f"{PARTIAL_PREFIX}{final.name}"
    try:
        with _exclusive_lock(backup_dir):
            kind_dir.mkdir(mode=DIRECTORY_MODE, exist_ok=True)
            _delete_partials(kind_dir)
            finished = False
            try:
                _write_backup(partial, source, hooks)
                partial.rename(final)
                finished = True
            finally:
                # This attempt's own partial directory goes before the failure is
                # reported, whatever the failure was (D15).
                if not finished:
                    shutil.rmtree(partial, ignore_errors=True)
            if kind is BackupKind.PRE_MIGRATION:
                _replace_same_version(kind_dir, final)
            _rotate(kind_dir, keep)
    except (OSError, sqlite3.Error) as error:
        raise BackupError(f"backup into {final} failed: {error}") from error
    return final


def take_timed_backup_if_due(  # noqa: PLR0913 - the same arguments a backup takes
    *,
    backup_dir: Path,
    source: BackupSource,
    keep: int,
    backup_hours: float,
    now: datetime,
) -> Path | None:
    """A timed backup when one is due, else ``None``. The one place the check runs,
    for the start (D14 step 8) and for the loop that wakes every
    ``BACKUP_CHECK_SECONDS``.

    Raises:
        BackupError: The check or the backup failed.
        HubStoreMissingError: There is no store to back up.
    """
    if not timed_backup_due(backup_dir, now, backup_hours):
        return None
    return take_backup(
        BackupKind.TIMED, backup_dir=backup_dir, source=source, keep=keep, now=now
    )
