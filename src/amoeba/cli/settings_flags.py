"""The mapping between :class:`ProcessSettings` and command-line flags.

Flags, not environment variables: ``AMOEBA_STORE_DIR`` stays the project's
only environment read (D3), so there is no second source of truth. Every
default comes from ``ProcessSettings`` itself; none is repeated here.

Split out of ``main.py`` to keep that module near its line budget.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from amoeba.process.settings import (
    DEFAULT_CF_DATA_DIR,
    DEFAULT_SQ_RUNS_DIR,
    ProcessSettings,
)


def positive_int(text: str) -> int:
    """An argparse type for a count that must be at least 1.

    Zero would be accepted by ``int`` and silently stop the queue (a batch of
    none) or park every file on its first failure — so it is refused here.
    """
    value = int(text)
    if value < 1:
        raise argparse.ArgumentTypeError(f"must be at least 1, got {value}")
    return value


def add_start_flags(parser: argparse.ArgumentParser) -> None:
    """Expose every :class:`ProcessSettings` tunable ``start`` uses."""
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
        "--clock-tolerance",
        type=float,
        default=defaults.clock_tolerance_seconds,
        metavar="SECONDS",
        help=(
            "Legacy matching only: clock skew allowed when matching a Squadron "
            "run's start time."
        ),
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
        help=(
            "Legacy matching only: the Squadron runs directory scanned for "
            "sq_run entries journaled before they carried a run id."
        ),
    )
    parser.add_argument(
        "--launch-grace",
        type=float,
        default=defaults.launch_grace_seconds,
        metavar="SECONDS",
        help=(
            "How long after a launch Squadron may still be creating the run "
            "before 'no run state' means the launch did not happen."
        ),
    )
    parser.add_argument(
        "--inbox-batch-size",
        type=positive_int,
        default=defaults.inbox_batch_size,
        metavar="COUNT",
        help="The most inbox files one tick handles.",
    )
    parser.add_argument(
        "--inbox-max-attempts",
        type=positive_int,
        default=defaults.inbox_max_attempts,
        metavar="COUNT",
        help="Failed applies of one file before it is parked in inbox/failed/.",
    )
    parser.add_argument(
        "--review-scan-interval",
        type=float,
        default=defaults.review_scan_interval_seconds,
        metavar="SECONDS",
        help="How often watched review directories are scanned.",
    )
    parser.add_argument(
        "--sq-timeout",
        type=float,
        default=defaults.sq_timeout_seconds,
        metavar="SECONDS",
        help="How long to wait for 'sq --version' at start-up.",
    )
    parser.add_argument(
        "--cf-data-dir",
        type=Path,
        default=DEFAULT_CF_DATA_DIR,
        metavar="PATH",
        help="The Context Forge data directory holding projects.json.",
    )


def add_stop_flags(parser: argparse.ArgumentParser) -> None:
    """Expose the one :class:`ProcessSettings` tunable ``stop`` consumes.

    ``stop`` uses only ``stop_timeout_seconds``; the rest governs the running
    loop and has no meaning to a command that just signals a PID and waits.
    Keeping it off ``start`` keeps both ``--help`` outputs honest.
    """
    defaults = ProcessSettings()

    parser.add_argument(
        "--stop-timeout",
        type=float,
        default=defaults.stop_timeout_seconds,
        metavar="SECONDS",
        help="How long to wait for the lock to be released after signalling.",
    )


def start_settings(args: argparse.Namespace) -> ProcessSettings:
    """Build ``start`` settings from parsed flags."""
    return ProcessSettings(
        idle_interval_seconds=args.idle_interval,
        shutdown_grace_seconds=args.shutdown_grace,
        clock_tolerance_seconds=args.clock_tolerance,
        cf_timeout_seconds=args.cf_timeout,
        sq_runs_dir=args.sq_runs_dir,
        inbox_batch_size=args.inbox_batch_size,
        inbox_max_attempts=args.inbox_max_attempts,
        review_scan_interval_seconds=args.review_scan_interval,
        sq_timeout_seconds=args.sq_timeout,
        cf_data_dir=args.cf_data_dir,
        launch_grace_seconds=args.launch_grace,
    )


def stop_settings(args: argparse.Namespace) -> ProcessSettings:
    """Build ``stop`` settings: only ``stop_timeout_seconds`` is reachable."""
    return ProcessSettings(stop_timeout_seconds=args.stop_timeout)
