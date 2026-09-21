"""``amoeba`` entry point: argument parsing, dispatch, and the one boundary.

This module owns two things the rest of the codebase deliberately does not:

1. :class:`ExitCode` — the whole exit-status vocabulary. No bare integer
   appears at any call site, and ``grep ExitCode src/amoeba/process/`` finds
   nothing: the process layer raises typed lifecycle errors, and mapping those
   to a status happens here.
2. :func:`main` — the **single** broad exception handler in the package, at the
   process boundary, where an uncaught exception would otherwise reach the user
   as a traceback. Every other ``except`` in this codebase is specific.
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Sequence
from enum import IntEnum
from importlib import metadata
from pathlib import Path
from typing import Any, Final

from amoeba.process.errors import (
    AlreadyRunningError,
    GraceExpiredError,
    ProcessError,
    StartupFailedError,
)
from amoeba.process.settings import DEFAULT_SQ_RUNS_DIR, ProcessSettings
from amoeba.store.models import StoreError

logger = logging.getLogger(__name__)

#: Recorded when the version cannot be resolved. An obvious placeholder rather
#: than a plausible-looking number.
UNKNOWN_VERSION: Final = "unknown"


def _installed_version() -> str:
    """The installed distribution's version, or an explicit placeholder."""
    try:
        return metadata.version("amoeba")
    except metadata.PackageNotFoundError:
        # Specific: running from a source tree with nothing installed. The
        # PID file's version field is informational and never drives a
        # decision, so a placeholder is correct here.
        return UNKNOWN_VERSION


#: Recorded in the PID file. Read from the installed distribution so it cannot
#: drift from what was actually installed.
VERSION: Final = _installed_version()


class ExitCode(IntEnum):
    """Every exit status this CLI produces, with the condition that causes it.

    Documented in ``docs/process-contract.md``. Defined once here so no call
    site writes a bare integer.
    """

    #: The command did what it was asked to do.
    OK = 0

    #: An unexpected failure reached the process boundary.
    FAILURE = 1

    #: ``start``: another process already holds the instance lock.
    ALREADY_RUNNING = 2

    #: ``stop``: nothing holds the instance lock.
    NOT_RUNNING = 3

    #: ``stop``: the process did not release the lock before the timeout.
    STOP_TIMEOUT = 4

    #: ``stop``: the lock is held but the PID file is absent or unreadable, so
    #: there is no PID that can safely be signalled.
    NO_STOP_TARGET = 5

    #: ``start``: a tenant did not return within the shutdown grace period.
    GRACE_EXPIRED = 6

    #: ``start``: a store could not be opened, or recovery could not complete.
    STARTUP_FAILED = 7

    #: ``status``: the supervisor is not running. Not a failure, but
    #: distinguishable from running by exit status alone.
    NOT_RUNNING_STATUS = 8


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for every subcommand."""
    parser = argparse.ArgumentParser(
        prog="amoeba",
        description=(
            "The Amoeba resident process and its read-only inspection surface."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    start = subparsers.add_parser(
        "start",
        help="Run the resident process in the foreground.",
        description=(
            "Runs in the foreground and logs to stderr. Detaching is the job "
            "of whatever launched it (launchd, tmux, a shell &)."
        ),
    )
    _add_settings_flags(start)

    subparsers.add_parser(
        "stop",
        help="Ask a running resident process to stop.",
        description=(
            "Sends SIGTERM to the recorded pid after confirming the lock is "
            "held, then waits for the lock to be released. Never escalates to "
            "SIGKILL."
        ),
    )

    subparsers.add_parser(
        "status", help="Report whether a resident process is running."
    )

    _add_inspect_parser(subparsers)

    return parser


def _add_settings_flags(parser: argparse.ArgumentParser) -> None:
    """Expose every :class:`ProcessSettings` tunable as a flag.

    Flags, not environment variables: ``AMOEBA_STORE_DIR`` stays the project's
    only environment read (D3), so there is no second source of truth.
    """
    defaults = ProcessSettings()

    parser.add_argument(
        "--idle-interval",
        type=float,
        default=defaults.idle_interval_seconds,
        metavar="SECONDS",
        help="How long the loop waits when no tenant reported work.",
    )
    parser.add_argument(
        "--shutdown-grace",
        type=float,
        default=defaults.shutdown_grace_seconds,
        metavar="SECONDS",
        help="How long shutdown waits for the current tick to return.",
    )
    parser.add_argument(
        "--stop-timeout",
        type=float,
        default=defaults.stop_timeout_seconds,
        metavar="SECONDS",
        help="How long 'stop' waits for the lock to be released.",
    )
    parser.add_argument(
        "--clock-tolerance",
        type=float,
        default=defaults.clock_tolerance_seconds,
        metavar="SECONDS",
        help="Clock skew allowed when matching a Squadron run's start time.",
    )
    parser.add_argument(
        "--cf-timeout",
        type=float,
        default=defaults.cf_timeout_seconds,
        metavar="SECONDS",
        help="How long to wait for a 'cf' invocation.",
    )
    parser.add_argument(
        "--sq-runs-dir",
        type=Path,
        default=DEFAULT_SQ_RUNS_DIR,
        metavar="PATH",
        help="The Squadron runs directory the observer scans.",
    )


def _add_inspect_parser(subparsers: Any) -> None:
    """Add ``inspect`` and one subcommand per registered listing.

    The subcommand names derive from the listing registry, never the reverse:
    the registry is the structural definition and the labels follow from it.

    ``subparsers`` is typed ``Any`` because argparse's subparsers-action type
    is private; it would have to be reached for through the module's internals
    to be named here. It is used only to call ``add_parser``.
    """
    from amoeba.cli.inspect import LISTINGS

    inspect = subparsers.add_parser(
        "inspect",
        help="Read-only listings over store contents.",
        description="Opens every store read-only. Never migrates, creates, or writes.",
    )
    listing_parsers = inspect.add_subparsers(dest="listing", required=True)

    for listing in LISTINGS:
        listing_parser = listing_parsers.add_parser(
            listing.name, help=listing.help_text
        )
        if listing.requires_project:
            listing_parser.add_argument(
                "--project", required=True, help="The project to list."
            )
        for flag, flag_help in listing.flags:
            listing_parser.add_argument(flag, action="store_true", help=flag_help)
        listing_parser.add_argument(
            "--json", action="store_true", help="Emit JSON instead of a table."
        )


def settings_from_args(args: argparse.Namespace) -> ProcessSettings:
    """Build settings from parsed flags. Defaults live in ``ProcessSettings``."""
    return ProcessSettings(
        idle_interval_seconds=args.idle_interval,
        shutdown_grace_seconds=args.shutdown_grace,
        stop_timeout_seconds=args.stop_timeout,
        clock_tolerance_seconds=args.clock_tolerance,
        cf_timeout_seconds=args.cf_timeout,
        sq_runs_dir=args.sq_runs_dir,
    )


def _dispatch(args: argparse.Namespace) -> ExitCode:
    """Route a parsed command to its implementation."""
    from amoeba.cli import inspect as inspect_module
    from amoeba.cli import lifecycle

    match args.command:
        case "start":
            return lifecycle.start(settings_from_args(args))
        case "stop":
            return lifecycle.stop(ProcessSettings())
        case "status":
            return lifecycle.status()
        case "inspect":
            return inspect_module.run_listing(args.listing, args, use_json=args.json)
        case _:
            raise ValueError(f"unhandled command {args.command!r}")


def main(argv: Sequence[str] | None = None) -> int:
    """Parse arguments, run the command, and map failures to exit codes.

    This is the **one documented process-boundary handler** in the package.
    Every typed failure the process layer raises is mapped here, and anything
    unexpected is logged with a traceback and reported as
    :attr:`ExitCode.FAILURE` rather than reaching the user raw.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )

    args = build_parser().parse_args(argv)

    try:
        return int(_dispatch(args))
    except AlreadyRunningError as error:
        print(f"amoeba: {error}", file=sys.stderr)
        return int(ExitCode.ALREADY_RUNNING)
    except GraceExpiredError as error:
        print(f"amoeba: {error}", file=sys.stderr)
        return int(ExitCode.GRACE_EXPIRED)
    except StartupFailedError as error:
        print(f"amoeba: {error}", file=sys.stderr)
        return int(ExitCode.STARTUP_FAILED)
    except StoreError as error:
        # The store's own message reaches the operator; the process never
        # falls back to a different store or starts with a project skipped.
        print(f"amoeba: {error}", file=sys.stderr)
        return int(ExitCode.STARTUP_FAILED)
    except ProcessError as error:
        print(f"amoeba: {error}", file=sys.stderr)
        return int(ExitCode.FAILURE)
    except KeyboardInterrupt:
        # Ctrl-C outside the running loop; a clean stop, not a crash.
        return int(ExitCode.OK)
    except Exception:
        # The process boundary. Documented as such per the project exception
        # rule: this is the only broad handler in the package, and it logs a
        # full traceback rather than swallowing anything.
        logger.exception("unexpected failure")
        return int(ExitCode.FAILURE)


if __name__ == "__main__":  # pragma: no cover - module entry point
    sys.exit(main())
