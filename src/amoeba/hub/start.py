"""The start sequence of `amoeba hub serve`, steps 2 to 8 (slice 260, D14, D5).

Step 1, the guard, is the first line of every hub command (``cli.hub_commands``).
This module runs the rest up to the point of serving, so tests run it without serving
and ``serve`` needs only the bound socket and the config it returns. Steps 3 to 7
failing raise ``HubStartError`` with one line; step 2's ``HubConfigError`` passes
through unchanged.
"""

from __future__ import annotations

import logging
import socket
import sqlite3
import sys
from collections.abc import Callable
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Final

from amoeba.config.home import StateLayout
from amoeba.hub.backups import (
    BackupError,
    BackupKind,
    BackupSource,
    newest_complete_backup,
    take_backup,
    take_timed_backup_if_due,
)
from amoeba.hub.certificate import (
    CertificateHooks,
    StartDecision,
    StartKind,
    classify_start,
    make_certificate,
)
from amoeba.hub.errors import HubStartError
from amoeba.hub.hub_config import HubConfig, load_hub_config
from amoeba.hub.restore import PARTIAL_DIR_NAME, RestoreHooks, restore_from_backup
from amoeba.hub.store_open import open_hub_store
from amoeba.store.errors import StoreError
from amoeba.store.migrations import EXPECTED_SCHEMA_VERSION, read_schema_version

logger = logging.getLogger(__name__)

#: How many connections may wait to be accepted before a refusal.
LISTEN_BACKLOG: Final = 128
NEW_CERTIFICATE_NOTICE: Final = (
    "the hub's certificate is new: every machine must be invited with "
    "`amoeba hub invite <machine>` and joined again with `amoeba join <line>`"
)
FROM_BACKUP_FLAG: Final = "--from-backup"
#: Starting kinds that find no store, so step 7 makes one.
_MAKES_THE_STORE: Final = frozenset(
    {
        StartKind.FIRST_PAIR_KEPT,
        StartKind.FIRST_LONE_FILE_REPLACED,
        StartKind.FIRST_START,
    }
)
#: Starting kinds that make a new certificate pair.
_MAKES_A_PAIR: Final = frozenset(
    {
        StartKind.DAMAGED_NEW_PAIR,
        StartKind.FIRST_LONE_FILE_REPLACED,
        StartKind.FIRST_START,
    }
)


@dataclass(frozen=True)
class StartHooks:
    """The fault seam of a start. Production passes none."""

    certificate: CertificateHooks = CertificateHooks()  # noqa: RUF009  frozen
    restore: RestoreHooks = RestoreHooks()  # noqa: RUF009  frozen
    #: Called after the certificate pair is made and before step 7.
    before_store_step: Callable[[], None] | None = None


@dataclass(frozen=True)
class PreparedHub:
    """What serving needs, and what the start has to report."""

    config: HubConfig
    #: Bound, not yet serving; uvicorn serves it.
    listener: socket.socket
    #: The directory a restore moved the old files to, for ``serve`` to print.
    replaced: Path | None


def _bind(config: HubConfig) -> socket.socket:
    """Step 3: bind the listening socket before anything is written."""
    try:
        family, kind, protocol, _name, address = socket.getaddrinfo(
            config.bind,
            config.port,
            type=socket.SOCK_STREAM,
            flags=socket.AI_PASSIVE,
        )[0]
        listener = socket.socket(family, kind, protocol)
    except OSError as error:
        raise HubStartError(
            f"cannot listen on {config.bind}:{config.port}: {error}"
        ) from error
    try:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(address)
        listener.listen(LISTEN_BACKLOG)
    except OSError as error:
        listener.close()
        raise HubStartError(
            f"cannot listen on {config.bind}:{config.port}: {error}"
        ) from error
    return listener


def _refusal(decision: StartDecision, backup: Path | None, layout: StateLayout) -> str:
    """The one-line refusal of a damaged or lost state, with both ways on (D5)."""
    restore = f"`amoeba hub serve {FROM_BACKUP_FLAG} <backup directory>`"
    if decision.kind is StartKind.LOST_REFUSED:
        return (
            f"the hub has no store at {layout.store_path}, but {backup} is a backup of "
            f"one. To bring the hub back run {restore}, or, to start a new and empty "
            "hub on purpose, set `backup_dir` in hub.yaml to an empty directory"
        )
    return (
        f"the hub's store is at {layout.store_path} but {', '.join(decision.missing)} "
        f"is missing, and {backup} is a backup. To bring the old hub back run "
        f"{restore}; to keep this store's records and invite every machine again, "
        "set `backup_dir` in hub.yaml to an empty directory"
    )


def _decide(
    layout: StateLayout, config: HubConfig
) -> tuple[StartDecision, Path | None]:
    """Step 5's facts and decision. The backup is read only where it decides."""
    has_store = layout.store_path.exists()
    has_cert = layout.hub_cert.exists()
    has_key = layout.hub_key.exists()
    backup: Path | None = None
    if not (has_store and has_cert and has_key):
        try:
            backup = newest_complete_backup(config.backup_path)
        except BackupError as error:
            raise HubStartError(str(error)) from error
    return classify_start(has_store, has_cert, has_key, backup is not None), backup


def _make_pair(layout: StateLayout, hooks: CertificateHooks) -> None:
    """A lone file is deleted, then a new pair is made, key first."""
    layout.hub_cert.unlink(missing_ok=True)
    layout.hub_key.unlink(missing_ok=True)
    try:
        make_certificate(layout.hub_cert, layout.hub_key, hooks)
    except OSError as error:
        raise HubStartError(f"cannot make the hub's certificate: {error}") from error


def _backup_source(layout: StateLayout) -> BackupSource:
    return BackupSource(layout.store_path, layout.hub_cert, layout.hub_key)


def _schema_version(store_path: Path) -> int:
    """Step 7: the stamped version, read on a plain connection, never migrating."""
    try:
        with closing(sqlite3.connect(f"{store_path.as_uri()}?mode=ro", uri=True)) as c:
            return read_schema_version(c)
    except (sqlite3.Error, StoreError) as error:
        raise HubStartError(
            f"cannot read the store at {store_path}: {error}"
        ) from error


def _open_store(
    layout: StateLayout, config: HubConfig, create: bool, now: datetime
) -> None:
    """Step 7: a pre-migration backup when the schema is behind, then open (which
    migrates), or make the store on a first start."""
    if not create:
        version = _schema_version(layout.store_path)
        if version < EXPECTED_SCHEMA_VERSION:
            try:
                take_backup(
                    BackupKind.PRE_MIGRATION,
                    backup_dir=config.backup_path,
                    source=_backup_source(layout),
                    keep=config.backups_kept,
                    now=now,
                    schema_version=version,
                )
            except BackupError as error:
                raise HubStartError(
                    f"{error}; the store at {layout.store_path} is not migrated"
                ) from error
    try:
        open_hub_store(layout, create=create).close()
    except StoreError as error:
        raise HubStartError(str(error)) from error


def _first_timed_backup(layout: StateLayout, config: HubConfig, now: datetime) -> None:
    """Step 8: a timed backup if one is due. A failure is logged and the start goes
    on."""
    try:
        take_timed_backup_if_due(
            backup_dir=config.backup_path,
            source=_backup_source(layout),
            keep=config.backups_kept,
            backup_hours=config.backup_hours,
            now=now,
        )
    except BackupError:
        # A full or unwritable backup disk must not keep the hub down: the failure
        # is logged at error level and the backup loop tries again at its next check.
        logger.exception("the timed backup at start failed")


def prepare_start(
    layout: StateLayout,
    *,
    now: datetime,
    start_log: Callable[[HubConfig], object],
    from_backup: Path | None = None,
    hooks: StartHooks = StartHooks(),  # noqa: B008  frozen, no state to share
) -> PreparedHub:
    """Steps 2 to 8 of the start. Raises ``HubConfigError`` for step 2 and
    ``HubStartError`` for steps 3 to 7; a taken port stops it before any file is
    written.

    ``start_log`` is step 6: it puts the rotating hub log on the root logger. The
    caller gives it, so a test can start without leaving a handler behind.
    """
    config = load_hub_config(layout.hub_file)
    listener = _bind(config)
    prepared = False
    try:
        replaced = _restore_or_refuse(layout, config, from_backup, now, hooks)
        decision, backup = _decide(layout, config)
        if decision.kind.is_refusal:
            raise HubStartError(_refusal(decision, backup, layout))
        if decision.kind in _MAKES_A_PAIR:
            _make_pair(layout, hooks.certificate)
        if decision.kind is StartKind.DAMAGED_NEW_PAIR:
            sys.stderr.write(f"amoeba hub: {NEW_CERTIFICATE_NOTICE}\n")
        start_log(config)
        if decision.kind is StartKind.DAMAGED_NEW_PAIR:
            logger.warning(NEW_CERTIFICATE_NOTICE)
        if hooks.before_store_step is not None:
            hooks.before_store_step()
        _open_store(layout, config, decision.kind in _MAKES_THE_STORE, now)
        _first_timed_backup(layout, config, now)
        prepared = True
    finally:
        # A start that stops anywhere gives the port back; the failure propagates.
        if not prepared:
            listener.close()
    return PreparedHub(config, listener, replaced)


def _restore_or_refuse(
    layout: StateLayout,
    config: HubConfig,
    from_backup: Path | None,
    now: datetime,
    hooks: StartHooks,
) -> Path | None:
    """Step 4: restore when asked; otherwise refuse while a restore is unfinished."""
    if from_backup is not None:
        return restore_from_backup(
            from_backup, layout.state_home, now, config.backups_kept, hooks.restore
        )
    if (layout.state_home / PARTIAL_DIR_NAME).exists():
        raise HubStartError(
            f"a restore did not finish ({layout.state_home / PARTIAL_DIR_NAME} is "
            f"there); run `amoeba hub serve {FROM_BACKUP_FLAG} <backup directory>` "
            "again with the same backup"
        )
    return None
