"""The resident process the contract proof runs: the shipped tenants + ProofRunner.

Run as ``python -m contract.bootstrap`` with ``PYTHONPATH`` at ``tests/``, never
through ``uv run`` (a temporary ``HOME`` would move uv's cache). Everything
per-run arrives as an argument. ``ProcessSettings`` keeps its default
``sq_runs_dir``, which derives from ``HOME``, so this process and
``amoeba prune`` agree on the runs directory by construction.
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Sequence
from pathlib import Path

from host_harness import READY_MARKER

from amoeba.process import (
    ProcessSettings,
    ResidentProcess,
    standard_tenants,
)
from contract.runner_tenant import ProofRunner
from contract.scenario import STANDIN_RUN_AGE

#: The proof is paced by the stand-in, not by wall-clock politeness: short
#: intervals keep each step quick.
IDLE_INTERVAL_SECONDS = 0.05
REVIEW_SCAN_INTERVAL_SECONDS = 0.2
SHUTDOWN_GRACE_SECONDS = 5.0

#: The proof restarts straight after a crash, so a real launch grace would stall
#: every restart step for up to a minute. The stand-in's side effects are
#: instantaneous, so none is needed: no run state at restart means not launched.
LAUNCH_GRACE_SECONDS = 0.0

#: Recorded in the PID file. Informational.
PROCESS_VERSION = "contract-proof"

_PROJECT_SEPARATOR = "="


class ReadyAnnouncer:
    """Prints the readiness marker on its first tick, then does nothing.

    Tenants tick only after recovery has run for every project, so the marker
    means "recovered and running", not merely "the interpreter started".
    """

    name = "ready-announcer"

    def __init__(self) -> None:
        self._announced = False

    def tick(self, host: ResidentProcess) -> bool:
        if not self._announced:
            self._announced = True
            print(READY_MARKER, flush=True)
        return False


def _reviews_dir(text: str) -> tuple[str, Path]:
    project_id, separator, directory = text.partition(_PROJECT_SEPARATOR)
    if not separator or not project_id or not directory:
        raise argparse.ArgumentTypeError(
            f"expected PROJECT{_PROJECT_SEPARATOR}PATH, got {text!r}"
        )
    return project_id, Path(directory)


def parse_arguments(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="contract.bootstrap")
    parser.add_argument("--supervisor-dir", type=Path, required=True)
    parser.add_argument("--cf-data-dir", type=Path, required=True)
    parser.add_argument(
        "--reviews-dir", type=_reviews_dir, action="append", required=True
    )
    parser.add_argument("--run-fixture", type=Path, required=True)
    parser.add_argument("--review-fixture", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str]) -> None:
    arguments = parse_arguments(argv)
    logging.basicConfig(level=logging.INFO, stream=sys.stderr)

    settings = ProcessSettings(
        idle_interval_seconds=IDLE_INTERVAL_SECONDS,
        review_scan_interval_seconds=REVIEW_SCAN_INTERVAL_SECONDS,
        shutdown_grace_seconds=SHUTDOWN_GRACE_SECONDS,
        cf_data_dir=arguments.cf_data_dir,
        launch_grace_seconds=LAUNCH_GRACE_SECONDS,
    )
    runner = ProofRunner(
        settings.sq_runs_dir,
        dict(arguments.reviews_dir),
        arguments.run_fixture,
        arguments.review_fixture,
        STANDIN_RUN_AGE,
    )
    process = ResidentProcess(
        settings,
        store_dir=arguments.supervisor_dir,
        version=PROCESS_VERSION,
        tenants=(
            *standard_tenants(settings, arguments.supervisor_dir),
            runner,
            ReadyAnnouncer(),
        ),
        # As `amoeba start` does: a tenant that never returns must not hold
        # the process forever.
        exit_on_grace_expiry=True,
    )
    process.install_signal_handlers()
    process.run()


if __name__ == "__main__":
    main(sys.argv[1:])
