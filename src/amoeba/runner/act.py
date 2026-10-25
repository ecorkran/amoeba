"""The act stage: issue each decided action as a journaled command (D9).

Moved out of ``ProjectTick`` so the tick stays under the size guideline and the
continuation acts (slice 127) have a place to join. Behavior is unchanged: every
subprocess-starting action checks the budget first, and a store-only action does not.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from amoeba.process import RunPoll
from amoeba.runner import finish
from amoeba.runner.budget import TickBudget, TickResult
from amoeba.runner.decide import (
    Action,
    BlockHumanStep,
    LaunchRun,
    ObserveRun,
    ResumeRun,
    WriteSlicePointer,
)
from amoeba.runner.dispatch.observe_pointer import PointerStage
from amoeba.runner.dispatch.reissue import ReissueLaunch, begin_reissue
from amoeba.runner.faults import NodeContext, TickFaults
from amoeba.runner.launch import (
    PARAM_PARAMS,
    PARAM_PIPELINE,
    LaunchError,
    LaunchTracker,
    PopenFactory,
    build_argv,
    launch,
    mint_run_id,
)
from amoeba.runner.lifecycle.human_steps import block_human_step
from amoeba.runner.observed import LaunchFailed
from amoeba.runner.resolutions.act import Acted, ContinuationActs
from amoeba.store import PARAM_CHECKOUT, PARAM_RUN_ID, CommandKind, JournalEntry, Store


@dataclass(frozen=True)
class ActOutcome:
    """How the act stage ended, and whether it wrote or issued anything."""

    result: TickResult
    wrote: bool


class ActStage:
    """Issues one tick's decided actions. Built fresh for each tick."""

    def __init__(
        self,
        *,
        store: Store,
        supervisor_dir: Path,
        pointers: PointerStage,
        poll_run: Callable[[str], RunPoll],
        tracker: LaunchTracker,
        popen: PopenFactory,
        now: Callable[[], datetime],
        context: NodeContext,
        version_label: str,
    ) -> None:
        self._store = store
        self._supervisor_dir = supervisor_dir
        self._pointers = pointers
        self._poll_run = poll_run
        self._tracker = tracker
        self._popen = popen
        self._now = now
        self._context = context
        self._version_label = version_label
        self._continuations = ContinuationActs(
            store=store, poll_run=poll_run, version_label=version_label
        )

    def run(
        self, actions: Sequence[Action], budget: TickBudget, faults: TickFaults
    ) -> ActOutcome:
        """Issue each action in order; ``CUT_OFF`` when the budget runs out.

        ``faults`` collects expected faults an action meets (a failed pre-poll); the
        tick raises them after this stage.
        """
        wrote = False
        for action in actions:
            self._context.set(action.node_id)
            match action:
                case BlockHumanStep():
                    # Store-only actions are applied in one transaction and not
                    # journaled: there is no external side effect to recover (D9).
                    block_human_step(self._store, action)
                case LaunchRun(reissue_of=str()):
                    if not budget.allows_call():
                        return ActOutcome(TickResult.CUT_OFF, wrote)
                    self._reissue(action)
                case LaunchRun():
                    if not budget.allows_call():
                        return ActOutcome(TickResult.CUT_OFF, wrote)
                    self._launch(action)
                case WriteSlicePointer():
                    if not budget.allows_call():
                        return ActOutcome(TickResult.CUT_OFF, wrote)
                    self._pointers.write(self._store, action, budget)
                case ResumeRun() | ObserveRun():
                    acted = self._continuations.act(action, budget, faults)
                    if acted is Acted.CUT_OFF:
                        return ActOutcome(TickResult.CUT_OFF, wrote)
                    if acted is Acted.WAITED:
                        continue
            wrote = True
        self._context.clear()
        return ActOutcome(TickResult.COMPLETE, wrote)

    def _launch(self, action: LaunchRun) -> None:
        """Journal the command, then launch. A failed launch is recorded."""
        run_id = mint_run_id(self._now())
        build_argv(
            action.pipeline, run_id, action.params
        )  # ValueError before journaling
        entry = self._store.journal_issue(
            action.node_id,
            kind=CommandKind.SQ_RUN,
            parameters={
                PARAM_PIPELINE: action.pipeline,
                PARAM_PARAMS: dict(action.params),
                PARAM_RUN_ID: run_id,
                PARAM_CHECKOUT: str(action.checkout),
            },
        )
        self._start(entry)

    def _reissue(self, action: LaunchRun) -> None:
        """Repeat a launch recovery found never started, under its own id (D9)."""
        decision = begin_reissue(
            self._store, action, self._supervisor_dir, self._poll_run
        )
        if isinstance(decision, ReissueLaunch):
            self._start(decision.entry)

    def _start(self, entry: JournalEntry) -> None:
        """Launch a journaled entry. A launch that cannot start is recorded."""
        started = launch(entry, self._supervisor_dir, self._popen)
        if isinstance(started, LaunchError):
            failed = LaunchFailed(started.failure, None, started.detail)
            finish.record(self._store, entry, failed, self._version_label)
            return
        self._tracker.track(entry.id, started)
