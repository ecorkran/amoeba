"""Carry out a resolution on a run that already exists (slice 127, D4).

A continuation is an ``sq_run`` entry on the step with the continued entry's
``pipeline``, ``params``, ``run_id`` and ``checkout``, plus the keys that say what it
continues and which resolution it carries out. The run id is the continued one, never
minted. Nothing is journaled until the one pre-poll has answered and the budget
allows the next step, so a routine cut-off never leaves an entry with no launch
behind it.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from enum import StrEnum

from amoeba.process import RunOutcomeDocument, RunPoll
from amoeba.runner import finish
from amoeba.runner.budget import TickBudget
from amoeba.runner.decide import ObserveRun, ResumeRun
from amoeba.runner.faults import Fault, FaultKind, ResumeFailure, TickFaults
from amoeba.runner.launch import PARAM_PARAMS, PARAM_PIPELINE
from amoeba.runner.observed import ResumeFailed
from amoeba.runner.resolutions.judge import checkpoint_of
from amoeba.runner.resolutions.prepoll import Act, prepoll_decision
from amoeba.runner.resolutions.vocabulary import PARAM_RESUME_SKIPPED, Continuation
from amoeba.store import (
    PARAM_CHECKOUT,
    PARAM_CONTINUATION,
    PARAM_CONTINUES,
    PARAM_RESOLUTION,
    PARAM_RUN_ID,
    CommandKind,
    JournalEntry,
    Store,
)

type ContinuationAction = ResumeRun | ObserveRun

#: Parameters a continuation copies from the entry it continues.
_COPIED: tuple[str, ...] = (PARAM_PIPELINE, PARAM_PARAMS, PARAM_RUN_ID, PARAM_CHECKOUT)


class Acted(StrEnum):
    """What the act did, for the stage's accounting."""

    #: Something was written or issued.
    WROTE = "wrote"
    #: Nothing was written; the step is decided again next tick.
    WAITED = "waited"
    #: The budget refused; nothing was written.
    CUT_OFF = "cut_off"


def journal_continuation(
    store: Store,
    action: ContinuationAction,
    continued: JournalEntry,
    continuation: Continuation,
    resume_skipped: str | None = None,
) -> JournalEntry:
    """Journal the continuation entry. Raises if the continued entry lacks a key."""
    missing = [key for key in _COPIED if key not in continued.parameters]
    if missing:
        raise ValueError(f"entry {continued.id} lacks {missing} to be continued")
    parameters: dict[str, object] = {key: continued.parameters[key] for key in _COPIED}
    parameters[PARAM_CONTINUATION] = continuation.value
    parameters[PARAM_CONTINUES] = continued.id
    parameters[PARAM_RESOLUTION] = action.resolution
    if resume_skipped is not None:
        parameters[PARAM_RESUME_SKIPPED] = resume_skipped
    return store.journal_issue(
        action.node_id, kind=CommandKind.SQ_RUN, parameters=parameters
    )


class ContinuationActs:
    """Issues resumes and observations. Built once per act stage."""

    def __init__(
        self,
        *,
        store: Store,
        poll_run: Callable[[str], RunPoll],
        version_label: str,
    ) -> None:
        self._store = store
        self._poll_run = poll_run
        self._version_label = version_label

    def act(
        self, action: ContinuationAction, budget: TickBudget, faults: TickFaults
    ) -> Acted:
        """Poll once, then wait, record a missing run, observe, or launch."""
        if not budget.allows_call():
            return Acted.CUT_OFF
        continued = self._store.journal_entry(action.continues)
        if continued is None:
            raise ValueError(f"entry {action.continues} to continue does not exist")
        poll = self._poll_run(action.run_id)
        decision = prepoll_decision(action, poll, _paused_at(continued))
        match decision.act:
            case Act.WAIT:
                faults.add(_poll_fault(action, decision.detail))
                return Acted.WAITED
            case Act.RUN_MISSING:
                self._record_missing(action, continued, poll)
                return Acted.WROTE
            case Act.OBSERVE:
                if not budget.allows_call():
                    return Acted.CUT_OFF
                journal_continuation(
                    self._store,
                    action,
                    continued,
                    Continuation.OBSERVE,
                    decision.resume_skipped,
                )
                return Acted.WROTE
            case Act.LAUNCH:
                raise NotImplementedError("resume launch: Task 6.4b")

    def _record_missing(
        self, action: ContinuationAction, continued: JournalEntry, poll: RunPoll
    ) -> None:
        """The run is gone: journal the entry, then record the failed resume."""
        entry = journal_continuation(
            self._store, action, continued, _continuation_of(action)
        )
        document = poll if isinstance(poll, RunOutcomeDocument) else None
        finished = ResumeFailed(ResumeFailure.RUN_MISSING, None, "", document)
        finish.record(self._store, entry, finished, self._version_label)


def _continuation_of(action: ContinuationAction) -> Continuation:
    """What the entry for this action is: a resume's decision, or an observation."""
    return Continuation.OBSERVE if isinstance(action, ObserveRun) else action.decision


def _paused_at(continued: JournalEntry) -> datetime | None:
    checkpoint = checkpoint_of(continued)
    return None if checkpoint is None else checkpoint.paused_at


def _poll_fault(action: ContinuationAction, detail: str | None) -> Fault:
    return Fault(
        FaultKind.RUN_OBSERVATION_FAILED,
        f"continuation of {action.run_id}: {detail}",
        node_id=action.node_id,
        run_id=action.run_id,
    )
