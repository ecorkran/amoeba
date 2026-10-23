"""``runner_tenant``: validate, probe ``sq``, and build the Runner (D9, D10)."""

from __future__ import annotations

import logging
import subprocess
import time
from datetime import UTC, datetime
from functools import partial
from pathlib import Path
from typing import Final

from amoeba.process import ProcessSettings, StartupFailedError, poll_run
from amoeba.runner.decide import Planner
from amoeba.runner.launch import LAUNCH_LOGS_DIRNAME
from amoeba.runner.probes import probe_sq
from amoeba.runner.tenant import RunnerTenant

logger = logging.getLogger(__name__)

#: The planners production runs. Empty in slice 122: nothing launches yet.
#: Slice 125 adds the dispatch planner here.
PRODUCTION_PLANNERS: Final[tuple[Planner, ...]] = ()


def _now() -> datetime:
    return datetime.now(UTC)


def validate_settings(settings: ProcessSettings) -> None:
    """Refuse bounds that break the tick budget.

    Raises:
        StartupFailedError: Naming the first field that is not positive, or the
            call timeout when it is not below the shutdown grace period (so a
            stop waits for at most one call).
    """
    for name in (
        "tick_deadline_seconds",
        "tick_call_timeout_seconds",
        "run_poll_interval_seconds",
    ):
        value: float = getattr(settings, name)
        if value <= 0:
            raise StartupFailedError(f"{name} must be positive, got {value}")
    if settings.tick_call_timeout_seconds >= settings.shutdown_grace_seconds:
        raise StartupFailedError(
            f"tick_call_timeout_seconds ({settings.tick_call_timeout_seconds}) "
            f"must be less than shutdown_grace_seconds "
            f"({settings.shutdown_grace_seconds})"
        )


def runner_tenant(
    settings: ProcessSettings,
    supervisor_dir: Path,
    *,
    planners: tuple[Planner, ...] | None = None,
) -> RunnerTenant:
    """Build the Runner, or raise before the loop starts.

    Args:
        settings: The process settings; the new tick bounds are validated.
        supervisor_dir: Holds ``launch-logs/``, created here.
        planners: ``None`` selects :data:`PRODUCTION_PLANNERS`. A passed value
            (tests, later slices) is used as given.

    Raises:
        StartupFailedError: For a bad bound or a failed ``sq`` probe.
    """
    validate_settings(settings)
    (supervisor_dir / LAUNCH_LOGS_DIRNAME).mkdir(parents=True, exist_ok=True)
    probe_sq(settings, _now(), poll_run)
    logger.info("sq probe passed: `sq runs wait` has the shape the Runner needs")
    return RunnerTenant(
        settings=settings,
        supervisor_dir=supervisor_dir,
        planners=PRODUCTION_PLANNERS if planners is None else planners,
        popen=subprocess.Popen,
        cf_run=subprocess.run,
        poll=partial(poll_run, timeout_seconds=settings.tick_call_timeout_seconds),
        now=_now,
        monotonic=time.monotonic,
    )
