"""The plan stage of a tick: read each due link's plan and reconcile it (D5, D7, D8).

It runs after in-flight runs are polled and the link probes have run, so a run's
poll is never cut off by a plan read, and only links whose probe passed are read.
For each such link that the schedule says is due:

* a cut-off read applies nothing, logs a WARNING and leaves the link due;
* a failed read, or a complete one the safety rules partly refused, adds a
  ``plan_read_failed`` fault and counts as failed;
* a clean read is reconciled and counted complete.

A link whose last read failed replays its faults on every tick until a read of that
link succeeds (D8 closure), as ``LinkProbes`` does for a failed probe. The replay
covers only the links the project has now. Nothing here retries within a tick: the
next due read is the retry.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence

from amoeba.runner.budget import TickBudget, TickResult
from amoeba.runner.cf_call import CfRun
from amoeba.runner.faults import Fault, FaultKind, TickFaults
from amoeba.runner.lifecycle.cadence import PlanReadSchedule
from amoeba.runner.lifecycle.plan_read import (
    PlanRead,
    PlanReadCutOff,
    PlanReadFailed,
    read_plan,
)
from amoeba.runner.lifecycle.reconcile import reconcile
from amoeba.runner.lifecycle.tree import LifecycleTree
from amoeba.store import Store
from amoeba.store.models import NodeKind

logger = logging.getLogger(__name__)

type LinkKey = tuple[str, str]


class PlanStage:
    """Reads and reconciles the plans of a project's CF links, once per lifetime
    state: the schedule and the failures to replay live here."""

    def __init__(
        self, *, schedule: PlanReadSchedule, run: CfRun, timeout_seconds: float
    ) -> None:
        self._schedule = schedule
        self._run = run
        self._timeout_seconds = timeout_seconds
        self._failures: dict[LinkKey, tuple[Fault, ...]] = {}

    def run(
        self,
        store: Store,
        project_id: str,
        links: Sequence[str],
        probe_passed: Mapping[str, bool],
        budget: TickBudget,
        faults: TickFaults,
    ) -> tuple[TickResult, bool]:
        """Read every due, probed link; replay the faults of failed ones.

        Args:
            links: The project's CF links now.
            probe_passed: Link to whether its probe passed (``LinkProbes.results``).
            faults: The tick's faults; failures are added here.

        Returns:
            Whether the budget cut a read off, and whether anything was written.
        """
        wrote = False
        for link in links:
            if not probe_passed.get(link, False):
                continue
            snapshots = store.latest_cf_snapshots(project_id, link)
            if self._schedule.due(project_id, link, snapshots):
                result, link_wrote = self._read_link(store, project_id, link, budget)
                wrote = wrote or link_wrote
                if result is TickResult.CUT_OFF:
                    return TickResult.CUT_OFF, wrote
            for fault in self._failures.get((project_id, link), ()):
                faults.add(fault)
        return TickResult.COMPLETE, wrote

    def _read_link(
        self, store: Store, project_id: str, link: str, budget: TickBudget
    ) -> tuple[TickResult, bool]:
        tree = LifecycleTree(store.nodes_for_project(project_id))
        read = read_plan(
            link,
            _initiatives_with_linked_slices(tree, link),
            self._run,
            budget,
            self._timeout_seconds,
        )
        if isinstance(read, PlanReadCutOff):
            logger.warning("plan read for CF link %s cut off by the tick budget", link)
            self._schedule.record_cut_off(project_id, link)
            return TickResult.CUT_OFF, False
        if isinstance(read, PlanReadFailed):
            self._fail(project_id, link, [_fault(project_id, link, read.detail)])
            return TickResult.COMPLETE, False
        return TickResult.COMPLETE, self._reconcile(store, project_id, link, read)

    def _reconcile(
        self, store: Store, project_id: str, link: str, read: PlanRead
    ) -> bool:
        link_faults = TickFaults()
        wrote = reconcile(store, project_id, link, read, link_faults)
        if len(link_faults):
            self._fail(
                project_id,
                link,
                [_fault(project_id, link, f.detail) for f in link_faults],
            )
        else:
            self._failures.pop((project_id, link), None)
            self._schedule.record_complete(project_id, link)
        return wrote

    def _fail(self, project_id: str, link: str, faults: list[Fault]) -> None:
        self._schedule.record_failed(project_id, link)
        self._failures[(project_id, link)] = tuple(faults)
        for fault in faults:
            logger.warning("plan read for CF link %s failed: %s", link, fault.detail)


def _fault(project_id: str, link: str, detail: str) -> Fault:
    return Fault(
        FaultKind.PLAN_READ_FAILED, f"project {project_id}, CF link {link}: {detail}"
    )


def _initiatives_with_linked_slices(tree: LifecycleTree, link: str) -> set[int]:
    """Indexes of this link's linked initiatives that have linked slice children."""
    found: set[int] = set()
    for node in tree.nodes:
        if (
            node.kind is NodeKind.INITIATIVE
            and node.cf.project == link
            and node.cf.index is not None
            and any(
                child.kind is NodeKind.SLICE and child.cf.index is not None
                for child in tree.children(node)
            )
        ):
            found.add(node.cf.index)
    return found
