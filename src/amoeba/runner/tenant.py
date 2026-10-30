"""``RunnerTenant``: ticks every project, and isolates one project's faults (D8).

This module holds the Runner's one process-boundary broad catch. A store
failure or an upstream shape error re-raises and the process exits (100's
recovery takes over on restart); anything else is logged, escalated, and the
other projects still tick in the same call.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from datetime import datetime
from pathlib import Path
from typing import Final, Protocol

from amoeba.process import ProcessSettings, RunPoll, UpstreamShapeError
from amoeba.runner.budget import TickBudget, TickResult
from amoeba.runner.cf_call import CfRun
from amoeba.runner.decide import Planner
from amoeba.runner.faults import STORE_FAILURES, FaultKind, NodeContext, escalate
from amoeba.runner.launch import LaunchTracker, PopenFactory
from amoeba.runner.lifecycle.cadence import PlanReadSchedule
from amoeba.runner.lifecycle.plan_stage import PlanStage
from amoeba.runner.observe import RunObserver
from amoeba.runner.probes import LinkProbes
from amoeba.runner.project_config import ProjectConfig
from amoeba.runner.routing.table import RoutingTable
from amoeba.runner.tick import ProjectTick
from amoeba.store import Store

logger = logging.getLogger(__name__)

#: The tenant's name in logs and in the host's grace-expiry error.
RUNNER_TENANT_NAME: Final = "runner"


class RunnerHost(Protocol):
    """The part of ``ResidentProcess`` the Runner reads."""

    @property
    def project_ids(self) -> tuple[str, ...]:
        """The projects hosted now. Read every tick: projects can appear."""
        ...

    @property
    def stop_requested(self) -> bool:
        """Whether the process has been asked to stop."""
        ...

    def store_for(self, project_id: str) -> Store:
        """The read-write store of a hosted project."""
        ...


class RunnerTenant:
    """Implements ``Tenant``: observe, record, decide and act, per project."""

    def __init__(
        self,
        *,
        settings: ProcessSettings,
        supervisor_dir: Path,
        planners: Sequence[Planner],
        popen: PopenFactory,
        cf_run: CfRun,
        poll: Callable[[str], RunPoll],
        now: Callable[[], datetime],
        monotonic: Callable[[], float],
        version_label: str,
        routing_table: RoutingTable,
        project_config: ProjectConfig,
        amoeba_version: str,
    ) -> None:
        """Build the tenant; every collaborator is injected so tests never sleep.

        ``version_label`` is the ``sq --version`` label, captured once at start-up.
        ``routing_table``, ``project_config`` and ``amoeba_version`` are read once at
        start-up and held for the process's life; a restart is the only way to
        change them.
        ``amoeba_version`` is the installed package version, never confused with
        ``version_label``.
        """
        self._settings = settings
        self._version_label = version_label
        self._routing_table = routing_table
        self._project_config = project_config
        self._amoeba_version = amoeba_version
        self._supervisor_dir = supervisor_dir
        self._planners = tuple(planners)
        self._popen = popen
        self._cf_run = cf_run
        self._now = now
        self._monotonic = monotonic
        self.tracker = LaunchTracker()
        self._observer = RunObserver(
            supervisor_dir=supervisor_dir,
            tracker=self.tracker,
            poll=poll,
            now=now,
            monotonic=monotonic,
            launch_grace_seconds=settings.launch_grace_seconds,
            run_poll_interval_seconds=settings.run_poll_interval_seconds,
        )
        self._probes = LinkProbes(
            run=cf_run, timeout_seconds=settings.tick_call_timeout_seconds
        )
        self._plans = PlanStage(
            schedule=PlanReadSchedule(settings.plan_read_interval_seconds, monotonic),
            run=cf_run,
            timeout_seconds=settings.tick_call_timeout_seconds,
        )
        self._carried_over: tuple[str, ...] = ()

    @property
    def name(self) -> str:
        """Identifies the tenant in logs."""
        return RUNNER_TENANT_NAME

    def tick(self, host: RunnerHost) -> bool:
        """Tick the projects until the budget is spent.

        Returns:
            True only if something was written to a store or a command issued.
            A tick that only polled a running run returns False, so the loop
            idles between ticks instead of spinning.
        """
        self.tracker.reap()
        deadline = self._monotonic() + self._settings.tick_deadline_seconds
        budget = TickBudget(deadline, host, self._monotonic)
        order = self._order(host.project_ids)
        wrote = False
        carried: list[str] = []
        for position, project_id in enumerate(order):
            if not budget.allows_call():
                carried.extend(order[position:])
                break
            result, project_wrote = self._tick_project(host, project_id, budget)
            wrote = wrote or project_wrote
            if result is TickResult.CUT_OFF:
                carried.append(project_id)
        self._carried_over = tuple(carried)
        return wrote

    def _order(self, project_ids: tuple[str, ...]) -> tuple[str, ...]:
        """Projects a previous tick did not finish first, then the rest."""
        first = tuple(p for p in self._carried_over if p in project_ids)
        return first + tuple(p for p in project_ids if p not in first)

    def _tick_project(
        self, host: RunnerHost, project_id: str, budget: TickBudget
    ) -> tuple[TickResult, bool]:
        store = host.store_for(project_id)
        context = NodeContext()
        tick = ProjectTick(
            project_id=project_id,
            store=store,
            supervisor_dir=self._supervisor_dir,
            planners=self._planners,
            observer=self._observer,
            probes=self._probes,
            plans=self._plans,
            tracker=self.tracker,
            popen=self._popen,
            now=self._now,
            context=context,
            version_label=self._version_label,
            project_settings=self._project_config.for_project(project_id),
            cf_run=self._cf_run,
            call_timeout_seconds=self._settings.tick_call_timeout_seconds,
            amoeba_version=self._amoeba_version,
            auto_resume_limit=self._settings.auto_resume_limit,
        )
        try:
            return tick.run(budget), tick.wrote
        except (*STORE_FAILURES, UpstreamShapeError):
            # The process exits; recovery on restart reconciles what is open.
            logger.exception(
                "runner tick hit a store failure for project %s", project_id
            )
            raise
        except Exception as error:  # noqa: BLE001 - the Runner's one process boundary (D8)
            logger.exception("runner tick failed for project %s", project_id)
            # Not caught again: a failing escalation write means a broken store.
            escalate(store, project_id, context, FaultKind.UNEXPECTED_FAULT, error)
            return TickResult.COMPLETE, True
