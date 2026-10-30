"""``CheckStage``: the tick's pre-dispatch stage, called from ``tick.py``.

``tick.py`` is near its size limit, so the pre-dispatch reads live here and
``tick.py`` calls the stage in a few lines. The stage is built in
``ProjectTick.__init__`` beside the act stage.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from amoeba.runner.budget import TickBudget
from amoeba.runner.cf_call import CfRun
from amoeba.runner.decide import ProjectView
from amoeba.runner.dispatch.candidates import Candidate, launch_candidates
from amoeba.runner.dispatch.checkout_check import DispatchCheck
from amoeba.runner.dispatch.checkout_reads import (
    DispatchReadFailed,
    check_candidate,
    read_dispatch_facts,
)
from amoeba.runner.faults import Fault, FaultKind, NodeContext, TickFaults


@dataclass(frozen=True)
class DispatchStageResult:
    """The pre-dispatch results by node id, and whether the budget cut the pass short.

    A candidate with no entry has no result: its reads failed or were cut off.
    """

    checks: Mapping[str, DispatchCheck]
    cut_off: bool


class CheckStage:
    """Reads git and the target around the launches of one project."""

    def __init__(
        self,
        *,
        context: NodeContext,
        cf_run: CfRun,
        call_timeout_seconds: float,
    ) -> None:
        self._context = context
        self._cf_run = cf_run
        self._timeout_seconds = call_timeout_seconds

    def check_dispatch(
        self, view: ProjectView, budget: TickBudget, faults: TickFaults
    ) -> DispatchStageResult:
        """Read and check every launch or resume candidate (D5), until the budget ends.

        A read that fails adds a project-scoped ``checkout_read_failed`` fault and
        gives the candidate no result: the step is not blocked, because it is not at
        fault. A candidate the budget cut off also has no result; the tick then ends
        as cut off so the closure waits for a complete tick.
        """
        checks: dict[str, DispatchCheck] = {}
        for candidate in launch_candidates(
            view.current_slices, view.dispatch, view.checkout_holders
        ):
            self._context.set(candidate.node_id)
            reads = read_dispatch_facts(
                candidate, budget, self._cf_run, self._timeout_seconds
            )
            if reads is None:
                return DispatchStageResult(checks, True)
            if isinstance(reads, DispatchReadFailed):
                faults.add(_read_failed(candidate, reads))
                continue
            checks[candidate.node_id] = check_candidate(candidate, reads)
        return DispatchStageResult(checks, False)


def _read_failed(candidate: Candidate, failed: DispatchReadFailed) -> Fault:
    return Fault(
        FaultKind.CHECKOUT_READ_FAILED,
        f"{failed.command} gave no usable answer in {candidate.checkout.path}: "
        f"{failed.reason}",
        node_id=candidate.node_id,
        extra={
            "checkout": str(candidate.checkout.path),
            "command": failed.command,
            "reason": failed.reason,
        },
    )
