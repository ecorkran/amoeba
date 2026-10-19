"""``amoeba serve``: the store, inbox, and feed over HTTP, in the foreground.

The only module that imports ``amoeba.serve``. It loads the server (and so
uvicorn) only when ``serve`` runs, so no other command pays for it.
``ServeRefusedError`` is caught here, not in ``main.py``, for that reason.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

from amoeba.serve.settings import TOKEN_ENV_VAR, ServeSettings
from amoeba.store import paths

if TYPE_CHECKING:  # pragma: no cover - typing only
    from amoeba.cli.main import ExitCode


def add_serve_parser(subparsers: Any) -> None:
    """Add ``serve``. ``subparsers`` is typed ``Any`` for the reason in ``main.py``."""
    defaults = ServeSettings()
    serve = subparsers.add_parser(
        "serve",
        help="Serve the store, inbox, and feed over HTTP.",
        description=(
            f"Runs in the foreground until stopped. Binds to loopback unless a "
            f"token ({TOKEN_ENV_VAR}) and TLS files are given."
        ),
    )
    serve.add_argument("--host", default=defaults.host, help="The address to bind.")
    serve.add_argument(
        "--port", type=int, default=defaults.port, help="The TCP port to bind."
    )
    serve.add_argument(
        "--tls-cert", type=Path, default=defaults.tls_certfile, help="TLS certificate."
    )
    serve.add_argument(
        "--tls-key", type=Path, default=defaults.tls_keyfile, help="TLS private key."
    )


def run_serve(args: argparse.Namespace) -> ExitCode:
    """Run ``amoeba serve`` until stopped."""
    from amoeba.cli.main import ExitCode
    from amoeba.serve.policy import ServeRefusedError
    from amoeba.serve.server import ServeStartFailedError, run

    settings = ServeSettings(
        host=args.host,
        port=args.port,
        tls_certfile=args.tls_cert,
        tls_keyfile=args.tls_key,
    )
    # Read once. An empty variable is unset: it cannot be a usable token.
    token = os.environ.get(TOKEN_ENV_VAR) or None
    try:
        run(settings, token, paths.store_dir())
    except ServeRefusedError as error:
        print(f"amoeba: {error}", file=sys.stderr)
        return ExitCode.SERVE_REFUSED
    except ServeStartFailedError as error:
        print(f"amoeba: {error}", file=sys.stderr)
        return ExitCode.FAILURE
    return ExitCode.OK
