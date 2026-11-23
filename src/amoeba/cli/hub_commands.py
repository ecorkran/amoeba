"""``amoeba hub ...``: the hub and its admin commands, CLI-only (slice 260, D13, D14).

They are no ``OperationName`` and have no MCP tool. The first line of each refuses on a
machine with a client file, before ``hub.yaml`` is read or any file is written. This
module builds the layout and hands the hub the opener bound to it, so the hub never
imports ``wiring``. A rejected request is exit 1; ``HubStartError``, ``BackupError`` and
every operational error are exit 3 with one stderr line.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from functools import partial
from pathlib import Path
from typing import Any, Final

from amoeba.cli.exit_codes import EXIT_OK, EXIT_REJECTED
from amoeba.cli.output import print_text_or_json
from amoeba.config.home import CONFIG_FILE_NAME, StateLayout, state_layout
from amoeba.config.user_config import UserConfig, load_user_config
from amoeba.hub import admin
from amoeba.hub.app import create_app
from amoeba.hub.backups import (
    BACKUP_CHECK_SECONDS,
    BackupSource,
    take_timed_backup_if_due,
)
from amoeba.hub.calls import handle_call
from amoeba.hub.hub_config import HubConfig
from amoeba.hub.hub_log import start_hub_log
from amoeba.hub.serve import BackupCheck, make_server, run
from amoeba.hub.start import FROM_BACKUP_FLAG, prepare_start
from amoeba.hub.store_open import open_hub_store
from amoeba.operations.state_move import refuse_local_store_if_joined

HUB_COMMAND: Final = "hub"
ACTION: Final = "hub_action"
SERVE: Final = "serve"
INVITE: Final = "invite"
MACHINES: Final = "machines"
RM_MACHINE: Final = "rm-machine"
BACKUP: Final = "backup"


def register_hub(commands: Any, json_parent: argparse.ArgumentParser) -> None:
    hub = commands.add_parser(HUB_COMMAND, help="run the hub, and manage its machines")
    hub.set_defaults(cli_only=HUB_COMMAND)
    actions = hub.add_subparsers(dest=ACTION, required=True, metavar="ACTION")
    serve = actions.add_parser(SERVE, help="serve the store over the network door")
    serve.add_argument(
        FROM_BACKUP_FLAG,
        dest="from_backup",
        type=Path,
        metavar="DIR",
        help="restore this backup into the state directory first (one start only)",
    )
    invite = actions.add_parser(
        INVITE, parents=[json_parent], help="make a machine and print its join line"
    )
    invite.add_argument("machine", help="the machine's name")
    actions.add_parser(
        MACHINES, parents=[json_parent], help="list the machines that may call"
    )
    remove = actions.add_parser(
        RM_MACHINE, parents=[json_parent], help="end a machine's access"
    )
    remove.add_argument("machine", help="the machine's name")
    actions.add_parser(BACKUP, parents=[json_parent], help="take a timed backup now")


def _now() -> datetime:
    return datetime.now(UTC)


#: How the hub's ``config.yaml`` is named in a missing-file message.
HUB_USER_CONFIG_KIND: Final = "hub config.yaml"


def hub_config_loader(layout: StateLayout) -> Callable[[], UserConfig]:
    path = layout.hub_file.with_name(CONFIG_FILE_NAME)

    def load() -> UserConfig:
        return load_user_config(path, kind=HUB_USER_CONFIG_KIND)

    return load


def _timed_check(layout: StateLayout, config: HubConfig) -> BackupCheck:
    source = BackupSource(layout.store_path, layout.hub_cert, layout.hub_key)

    def check() -> object:
        return take_timed_backup_if_due(
            backup_dir=config.backup_path,
            source=source,
            keep=config.backups_kept,
            backup_hours=config.backup_hours,
            now=_now(),
        )

    return check


def run_serve(layout: StateLayout, from_backup: Path | None) -> int:
    """Start the hub (D14, steps 2 to 9) and serve until it is stopped."""

    def start_log(config: HubConfig) -> object:
        return start_hub_log(
            layout.hub_log, config.hub_log_max_bytes, config.hub_logs_kept
        )

    prepared = prepare_start(
        layout, now=_now(), start_log=start_log, from_backup=from_backup
    )
    if prepared.replaced is not None:
        sys.stderr.write(
            f"amoeba hub: the old files were moved to {prepared.replaced}\n"
        )
    config = prepared.config
    handle = partial(
        handle_call,
        open_store=partial(open_hub_store, layout),
        clock=_now,
        load_config=hub_config_loader(layout),
    )

    server = make_server(create_app(handle, _now), layout.hub_cert, layout.hub_key)
    run(
        server,
        prepared.listener,
        bind=config.bind,
        port=config.port,
        check_seconds=BACKUP_CHECK_SECONDS,
        run_check=_timed_check(layout, config),
    )
    return EXIT_OK


def _run_invite(layout: StateLayout, arguments: argparse.Namespace) -> int:
    made = admin.invite(layout, arguments.machine, _now())
    print_text_or_json(
        made.join_line,
        {"machine": made.machine, "join_line": made.join_line, "new": made.is_new},
        arguments.json,
    )
    return EXIT_OK


def _run_machines(layout: StateLayout, arguments: argparse.Namespace) -> int:
    rows = admin.machines(layout)
    text = "\n".join(
        f"{row.name}  token: {'yes' if row.has_token else 'no'}  last call: "
        f"{'never' if row.last_called_at is None else row.last_called_at.isoformat()}  "
        f"client: {row.client_version or 'unknown'}"
        for row in rows
    )
    print_text_or_json(
        text or "no machines",
        [
            {
                "name": row.name,
                "has_token": row.has_token,
                "last_called_at": (
                    None
                    if row.last_called_at is None
                    else row.last_called_at.isoformat()
                ),
                "client_version": row.client_version,
            }
            for row in rows
        ],
        arguments.json,
    )
    return EXIT_OK


def run_hub(arguments: argparse.Namespace) -> int:
    """Run a hub command; the first line is the guard (D2)."""
    layout = state_layout()
    refuse_local_store_if_joined(layout)
    action: str = getattr(arguments, ACTION)
    try:
        if action == SERVE:
            return run_serve(layout, arguments.from_backup)
        if action == INVITE:
            return _run_invite(layout, arguments)
        if action == MACHINES:
            return _run_machines(layout, arguments)
        if action == RM_MACHINE:
            admin.rm_machine(layout, arguments.machine)
            print_text_or_json(
                f"removed {arguments.machine}",
                {"removed": arguments.machine},
                arguments.json,
            )
            return EXIT_OK
        made = admin.backup(layout, _now())
        print_text_or_json(str(made), {"path": str(made)}, arguments.json)
        return EXIT_OK
    except admin.AdminRejection as rejection:
        sys.stderr.write(f"rejected: {rejection}\n")
        return EXIT_REJECTED
