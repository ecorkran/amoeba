"""Serving: ``uvicorn`` on the socket the start bound, and the backup loop (slice 260,
D14 step 9).

``uvicorn`` runs with its access log off and its own logging set-up off
(``log_config=None``), so what it logs goes through the root logger to the hub log
(D16). Nothing here adds a timeout or a connection cap of the hub's own (D14, "A peer
that stalls").
"""

from __future__ import annotations

import logging
import socket
import sys
from collections.abc import Callable
from pathlib import Path

import anyio
import anyio.to_thread
import uvicorn
from starlette.applications import Starlette

from amoeba.hub.backups import BackupError
from amoeba.store.errors import HubStoreMissingError

logger = logging.getLogger(__name__)

type BackupCheck = Callable[[], object]


def make_server(app: Starlette, cert_path: Path, key_path: Path) -> uvicorn.Server:
    """A ``uvicorn`` server for ``app`` over the hub's certificate and key."""
    config = uvicorn.Config(
        app,
        ssl_certfile=str(cert_path),
        ssl_keyfile=str(key_path),
        access_log=False,
        log_config=None,
    )
    return uvicorn.Server(config)


async def backup_loop(check_seconds: float, run_check: BackupCheck) -> None:
    """Every ``check_seconds``, run the timed-backup check in a worker thread."""
    while True:
        await anyio.sleep(check_seconds)
        try:
            await anyio.to_thread.run_sync(run_check)
        except (BackupError, HubStoreMissingError):
            # The failure is in the log at error level and the next check tries
            # again, so a full or unwritable backup disk, or a store file that went
            # missing (which a backup never replaces), never stops serving.
            logger.exception("the timed backup check failed")


async def serve(
    server: uvicorn.Server,
    listener: socket.socket,
    *,
    check_seconds: float,
    run_check: BackupCheck,
) -> None:
    """Serve on ``listener`` until the server is asked to stop; the backup loop runs
    beside it and ends with it."""
    async with anyio.create_task_group() as tasks:
        tasks.start_soon(backup_loop, check_seconds, run_check)
        await server.serve(sockets=[listener])
        tasks.cancel_scope.cancel()


def run(
    server: uvicorn.Server,
    listener: socket.socket,
    *,
    bind: str,
    port: int,
    check_seconds: float,
    run_check: BackupCheck,
) -> None:
    """Write the one serving line to stderr and serve until stopped (blocking)."""
    sys.stderr.write(f"amoeba hub: serving on {bind}:{port}\n")
    sys.stderr.flush()
    anyio.run(
        lambda: serve(
            server, listener, check_seconds=check_seconds, run_check=run_check
        )
    )
