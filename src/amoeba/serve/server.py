"""``run``: check the bind, then serve in the foreground until stopped (LLD D3, D7).

The only module that imports uvicorn's server, and only ``cli/serve.py``
imports it. uvicorn handles SIGTERM and Ctrl-C: it stops accepting, waits up to
the shutdown grace for open connections, then cancels the open streams.
"""

from __future__ import annotations

from pathlib import Path

import uvicorn

from amoeba.serve.app import build_app
from amoeba.serve.policy import check_bind
from amoeba.serve.settings import ServeSettings


class ServeStartFailedError(Exception):
    """uvicorn could not start (a port in use, a host with no such interface).

    uvicorn logs its own message and exits the process with its own status (3),
    which would collide with amoeba's exit codes; this carries the failure to
    the CLI instead, which exits ``FAILURE``.
    """


def run(settings: ServeSettings, token: str | None, store_dir: Path) -> None:
    """Serve until a signal stops the server.

    On SIGTERM or Ctrl-C, uvicorn shuts down within the grace and then
    re-raises the signal, so the process ends by that signal.

    Raises:
        ServeRefusedError: Before anything binds, if :func:`check_bind` refuses.
        ServeStartFailedError: If uvicorn could not start serving.
    """
    check_bind(settings, token)
    config = uvicorn.Config(
        build_app(settings, token, store_dir),
        host=settings.host,
        port=settings.port,
        ssl_certfile=settings.tls_certfile,
        ssl_keyfile=settings.tls_keyfile,
        timeout_graceful_shutdown=settings.shutdown_grace_seconds,
    )
    try:
        uvicorn.Server(config).run()
    except SystemExit as error:
        # Specific: uvicorn's start-up failure exit. Its message is logged.
        raise ServeStartFailedError(
            f"the server could not start (uvicorn exit status {error.code})"
        ) from error
