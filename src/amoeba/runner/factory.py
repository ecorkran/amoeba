"""``runner_tenant``: validate, probe ``sq``, and build the Runner (D9, D10)."""

from __future__ import annotations

import logging
import subprocess
import time
from datetime import UTC, datetime
from functools import partial
from pathlib import Path
from typing import Final

from amoeba.process import (
    ProcessSettings,
    StartupFailedError,
    capture_sq_version_label,
    poll_run,
)
from amoeba.runner.decide import Planner
from amoeba.runner.launch import LAUNCH_LOGS_DIRNAME
from amoeba.runner.lifecycle.human_steps import HumanStepPlanner
from amoeba.runner.probes import probe_sq
from amoeba.runner.tenant import RunnerTenant

logger = logging.getLogger(__name__)

#: The planners production runs: human steps (slice 124), over current steps only.
#: Slice 125 appends its dispatch planner here.
PRODUCTION_PLANNERS: Final[tuple[Planner, ...]] = (HumanStepPlanner(),)


def _now() -> datetime:
    return datetime.now(UTC)


def validate_settings(settings: ProcessSettings) -> None:
    """Refuse bounds that break the tick budget.

    Raises:
        StartupFailedError: Naming the first field that is not positive, or the
            call timeout when it is not below the shutdown grace period (so a
            stop waits for at most one call).
    """
    bounds = (
        ("tick_deadline_seconds", settings.tick_deadline_seconds),
        ("tick_call_timeout_seconds", settings.tick_call_timeout_seconds),
        ("run_poll_interval_seconds", settings.run_poll_interval_seconds),
        ("plan_read_interval_seconds", settings.plan_read_interval_seconds),
    )
    for name, value in bounds:
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
    # Once, at start: a recorded review whose file has no stamp is labelled with it.
    version_label = capture_sq_version_label(settings.sq_timeout_seconds)
    return RunnerTenant(
        settings=settings,
        supervisor_dir=supervisor_dir,
        planners=PRODUCTION_PLANNERS if planners is None else planners,
        popen=subprocess.Popen,
        cf_run=subprocess.run,
        poll=partial(poll_run, timeout_seconds=settings.tick_call_timeout_seconds),
        now=_now,
        monotonic=time.monotonic,
        version_label=version_label,
    )
