"""The answering stage: observe, settle what was stranded, launch what is pending (D10).

Three passes, in this order. The observe pass finishes the answering runs that
ended; the stranded pass declines an ``answering`` question whose run can no longer
settle it; the pending pass declines what cannot be answered and launches a run for
the rest, oldest first, up to the concurrency cap. A budget refusal stops the
launches and the polls but never the store-only declines. Nothing retries.
"""

from __future__ import annotations

from dataclasses import dataclass

from amoeba.runner.answering.finish import finish_answering
from amoeba.runner.answering.launch import LaunchContext, LaunchStatus, launch_answering
from amoeba.runner.answering.settle import (
    Decline,
    Launch,
    QuestionInvariantError,
    settle_pending,
)
from amoeba.runner.budget import TickBudget, TickResult
from amoeba.runner.faults import NodeContext, TickFaults
from amoeba.runner.observe import RunObserver
from amoeba.store import (
    BlockedState,
    CommandKind,
    DeclineReason,
    JournalEntry,
    JournalOutcome,
    QuestionRecord,
    QuestionState,
    Store,
)


def unresolved_answering_entries(store: Store, project_id: str) -> list[JournalEntry]:
    """The project's in-flight ``sq_answer`` entries, oldest first.

    The one place the observe pass and the concurrency cap read the set, so the cap
    always counts what is being observed.
    """
    return [
        entry
        for entry in store.unresolved_journal_entries(project_id)
        if entry.kind is CommandKind.SQ_ANSWER
    ]


@dataclass(frozen=True)
class StageResult:
    """Whether the stage ran out of budget, and whether it wrote."""

    cut_off: bool
    wrote: bool


class AnsweringStage:
    """The answering work of one project's tick.

    ``launch`` is ``None`` for a project with no ``answerer`` section: the stage
    then only declines (``answerer_not_configured``) and settles what is stranded.
    """

    def __init__(
        self,
        *,
        store: Store,
        project_id: str,
        launch: LaunchContext | None,
        observer: RunObserver,
        node_context: NodeContext,
    ) -> None:
        self._store = store
        self._project_id = project_id
        self._launch = launch
        self._observer = observer
        self._context = node_context
        self._wrote = False

    def run(self, budget: TickBudget, faults: TickFaults) -> StageResult:
        """Observe, then settle the stranded, then the pending."""
        self._wrote = False
        cut_off = self._observe(budget, faults)
        self._context.clear()
        self._settle_stranded()
        cut_off = self._settle_pending(budget) or cut_off
        return StageResult(cut_off, self._wrote)

    # -- observe ---------------------------------------------------------------

    def _observe(self, budget: TickBudget, faults: TickFaults) -> bool:
        """Finish each answering run that ended; whether the polls ran out of budget."""
        if self._launch is None:
            return False
        entries = unresolved_answering_entries(self._store, self._project_id)
        if not entries:
            return False
        observed = self._observer.observe(entries, budget, faults, self._context, {})
        # A failure past this point is about the project, not the node polled last.
        self._context.clear()
        for run in observed.runs:
            if run.finished is None:
                continue
            finish_answering(
                self._store, run.run.entry, run.finished, self._launch.settings
            )
            self._launch.tracker.forget(run.run.entry.id)
            self._wrote = True
        return observed.result is TickResult.CUT_OFF

    # -- stranded --------------------------------------------------------------

    def _settle_stranded(self) -> None:
        """Decline an ``answering`` question whose entry is resolved and unsettled."""
        for record in self._store.questions(
            self._project_id, state=QuestionState.ANSWERING
        ):
            entry = self._entry_of(record)
            if not entry.is_resolved or self._awaits_runner(record):
                continue
            self._store.decline_question(
                record.id,
                reason=_stranded_reason(entry),
                detail=_stranded_detail(entry),
            )
            self._wrote = True

    def _entry_of(self, record: QuestionRecord) -> JournalEntry:
        entry = (
            None
            if record.answering_entry_id is None
            else self._store.journal_entry(record.answering_entry_id)
        )
        if entry is None:
            raise QuestionInvariantError(
                f"answering question {record.id!r} has no journal entry"
            )
        return entry

    def _awaits_runner(self, record: QuestionRecord) -> bool:
        """Whether the record's block holds a resolution the Runner has yet to take."""
        return self._block_of(record).awaits_runner

    # -- pending ---------------------------------------------------------------

    def _settle_pending(self, budget: TickBudget) -> bool:
        """Decline or launch each pending question; whether a launch was cut off."""
        cut_off = False
        for record in self._store.pending_questions(self._project_id):
            settled = settle_pending(
                record,
                self._block_of(record),
                configured=self._launch is not None,
            )
            if isinstance(settled, Decline):
                self._store.decline_question(record.id, reason=settled.reason)
                self._wrote = True
            elif isinstance(settled, Launch) and not cut_off:
                cut_off = self._launch_one(record, budget)
        return cut_off

    def _launch_one(self, record: QuestionRecord, budget: TickBudget) -> bool:
        """Launch if there is a free slot; whether the budget refused."""
        launch = self._launch
        if launch is None:
            raise QuestionInvariantError("a launch was settled with no answerer")
        in_flight = len(unresolved_answering_entries(self._store, self._project_id))
        if in_flight >= launch.settings.max_concurrent_runs:
            return False
        status = launch_answering(launch, record, budget)
        self._wrote = self._wrote or status is not LaunchStatus.STOPPED
        return status is LaunchStatus.STOPPED

    def _block_of(self, record: QuestionRecord) -> BlockedState:
        block = (
            None
            if record.blocked_state_id is None
            else self._store.blocked_state(record.blocked_state_id)
        )
        if block is None:
            raise QuestionInvariantError(
                f"question {record.id!r} is linked to no block"
            )
        return block


def _stranded_reason(entry: JournalEntry) -> DeclineReason:
    """Recovery that found no run is a failed run; anything else is a discard."""
    if entry.outcome in (JournalOutcome.NOT_APPLIED, JournalOutcome.UNKNOWN):
        return DeclineReason.ANSWERING_RUN_FAILED
    return DeclineReason.ANSWER_DISCARDED


def _stranded_detail(entry: JournalEntry) -> str:
    outcome = "unresolved" if entry.outcome is None else entry.outcome.value
    return (
        f"the answering run's journal entry was resolved {outcome} and left no answer"
    )
