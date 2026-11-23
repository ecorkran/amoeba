"""The hub's admin commands (slice 260, D13): invite, machines, rm-machine, backup.

Each opens the store with ``open_hub_store``, which never creates one, so run on a hub
that has not finished its first start each raises ``HubStoreMissingError`` and writes
no file. ``invite`` opens the store before it reads the certificate, so a hub that never
started reports the missing store first.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from amoeba.config.home import StateLayout
from amoeba.hub.backups import BackupKind, BackupSource, take_backup
from amoeba.hub.errors import HubStartError
from amoeba.hub.hub_config import load_hub_config
from amoeba.hub.store_open import open_hub_store
from amoeba.store.machines import (
    MachineRow,
    hash_token,
    invite_machine,
    list_machines,
    remove_machine,
)
from amoeba.wire.fingerprint import fingerprint
from amoeba.wire.join_line import format_join_line
from amoeba.wire.protocol import is_machine_name

#: How many bytes of randomness a token carries: 256 bits.
TOKEN_BYTES = 32


class AdminRejection(Exception):
    """The command refused the request (exit 1): a malformed name or no such machine."""


@dataclass(frozen=True)
class Invited:
    """What `invite` made: the line to give the machine, and whether it is new."""

    machine: str
    join_line: str
    is_new: bool


def _certificate_pem(layout: StateLayout) -> str:
    if not layout.hub_cert.exists():
        raise HubStartError(
            f"the hub has no certificate at {layout.hub_cert}; run `amoeba hub serve` "
            "first, which makes it on a first start"
        )
    return layout.hub_cert.read_text(encoding="utf-8")


def invite(layout: StateLayout, name: str, now: datetime) -> Invited:
    """Make the machine, or give an existing one a new token, and return its join
    line. A re-invite ends the old token at once.

    Raises:
        AdminRejection: The name is malformed.
        HubStoreMissingError: The hub has not started yet.
        HubConfigError: ``hub.yaml`` is missing or bad.
        HubStartError: The hub's certificate is missing.
    """
    if not is_machine_name(name):
        raise AdminRejection(
            f"{name!r} is not a machine name: lower-case letters, digits, '.', '_' "
            "and '-', starting with a letter or digit, at most 64 characters"
        )
    with open_hub_store(layout) as store:
        config = load_hub_config(layout.hub_file)
        pem = _certificate_pem(layout)
        token = secrets.token_urlsafe(TOKEN_BYTES)
        with store.write() as transaction:
            is_new = invite_machine(transaction, name, hash_token(token), now)
    return Invited(
        name, format_join_line(config.address, fingerprint(pem), token), is_new
    )


def machines(layout: StateLayout) -> list[MachineRow]:
    """Every machine: name, whether it has a token, last call and client version."""
    with open_hub_store(layout) as store, store.read() as transaction:
        return list_machines(transaction)


def rm_machine(layout: StateLayout, name: str) -> None:
    """Delete the machine, its sessions, checkouts and kept results in one transaction.

    Raises:
        AdminRejection: There is no such machine.
    """
    with open_hub_store(layout) as store, store.write() as transaction:
        if not remove_machine(transaction, name):
            raise AdminRejection(f"no machine named {name!r}")


def backup(layout: StateLayout, now: datetime) -> Path:
    """Take a timed backup now and return its directory; safe while the hub serves.

    Raises:
        HubStoreMissingError: The hub has no store to back up.
        HubConfigError: ``hub.yaml`` is missing or bad.
        BackupError: The backup failed.
    """
    open_hub_store(layout).close()
    config = load_hub_config(layout.hub_file)
    return take_backup(
        BackupKind.TIMED,
        backup_dir=config.backup_path,
        source=BackupSource(layout.store_path, layout.hub_cert, layout.hub_key),
        keep=config.backups_kept,
        now=now,
    )
