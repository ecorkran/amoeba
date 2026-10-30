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
from enum import StrEnum
from pathlib import Path

from amoeba.process import RunOutcomeDocument, RunPoll
from amoeba.runner import finish
from amoeba.runner.budget import TickBudget
from amoeba.runner.decide import ObserveRun, ResumeRun
from amoeba.runner.faults import Fault, FaultKind, ResumeFailure, TickFaults
from amoeba.runner.launch import (
    PARAM_PARAMS,
    PARAM_PIPELINE,
    LaunchError,
    LaunchTracker,
    PopenFactory,
    log_paths,
    spawn,
)
from amoeba.runner.observed import ResumeFailed
from amoeba.runner.resolutions.argv import resume_argv
from amoeba.runner.resolutions.confirm import resumed_from_entry
from amoeba.runner.resolutions.prepoll import Act, prepoll_decision
from amoeba.runner.resolutions.vocabulary import (
    PARAM_RESUME_CAUSE,
    PARAM_RESUME_SKIPPED,
    Continuation,
    ResumeCause,
)
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
    if action.resolution is not None:
        parameters[PARAM_RESOLUTION] = action.resolution
    if resume_skipped is not None:
        parameters[PARAM_RESUME_SKIPPED] = resume_skipped
    if isinstance(action, ResumeRun):
        parameters[PARAM_RESUME_CAUSE] = action.cause.value
        parameters.update(action.journal_extra)
    return store.journal_issue(
        action.node_id, kind=CommandKind.SQ_RUN, parameters=parameters
    )


class ContinuationActs:
    """Issues resumes and observations. Built once per act stage."""

    def __init__(
        self,
        *,
        store: Store,
        supervisor_dir: Path,
        poll_run: Callable[[str], RunPoll],
        tracker: LaunchTracker,
        popen: PopenFactory,
        version_label: str,
    ) -> None:
        self._store = store
        self._supervisor_dir = supervisor_dir
        self._poll_run = poll_run
        self._tracker = tracker
        self._popen = popen
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
        decision = prepoll_decision(action, poll, resumed_from_entry(continued))
        match decision.act:
            case Act.WAIT:
                if decision.detail is None:
                    raise ValueError("a WAIT decision carries its poll failure text")
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
                if not budget.allows_call():
                    return Acted.CUT_OFF
                self._launch(action, continued, poll)
                return Acted.WROTE

    def _launch(
        self, action: ContinuationAction, continued: JournalEntry, poll: RunPoll
    ) -> None:
        """Journal the entry, then start ``sq run --resume`` detached (D4 step 3).

        Only the journal write, a store call, runs between the budget check and the
        spawn. A spawn that fails is recorded as a failed resume, never retried.
        """
        if not isinstance(action, ResumeRun):
            raise ValueError(f"{action.node_id}: only a resume launches")
        entry = journal_continuation(self._store, action, continued, action.decision)
        argv = resume_argv(action.run_id, action.decision, self._instructions(action))
        started = spawn(
            argv,
            str(action.checkout),
            log_paths(self._supervisor_dir, entry.id),
            self._popen,
        )
        if isinstance(started, LaunchError):
            document = poll if isinstance(poll, RunOutcomeDocument) else None
            failed = ResumeFailed(
                ResumeFailure.SPAWN_ERROR, None, started.detail, document
            )
            finish.record_unstarted(self._store, entry, failed)
            return
        self._tracker.track(entry.id, started)

    def _instructions(self, action: ResumeRun) -> str | None:
        """The instructions for the resume.

        A resolution resume reads the PM's text from the resolution slot, here and
        nowhere else, so it is never journaled or held in an action. An automatic
        resume carries its own, if any.
        """
        if action.cause is ResumeCause.TRANSIENT:
            return action.instructions
        if action.resolution is None:
            raise ValueError(f"a resolution resume of {action.node_id} names none")
        blocked = self._store.blocked_state(action.resolution)
        if blocked is None or blocked.resolution is None:
            raise ValueError(f"resolution {action.resolution} has no resolution slot")
        return blocked.resolution.instructions

    def _record_missing(
        self, action: ContinuationAction, continued: JournalEntry, poll: RunPoll
    ) -> None:
        """The run is gone: journal the entry, then record the failed resume."""
        entry = journal_continuation(
            self._store, action, continued, _continuation_of(action)
        )
        document = poll if isinstance(poll, RunOutcomeDocument) else None
        finished = ResumeFailed(ResumeFailure.RUN_MISSING, None, "", document)
        finish.record_unstarted(self._store, entry, finished)


def _continuation_of(action: ContinuationAction) -> Continuation:
    """What the entry for this action is: a resume's decision, or an observation."""
    return Continuation.OBSERVE if isinstance(action, ObserveRun) else action.decision


def _poll_fault(action: ContinuationAction, detail: str) -> Fault:
    return Fault(
        FaultKind.RUN_OBSERVATION_FAILED,
        f"continuation of {action.run_id}: {detail}",
        node_id=action.node_id,
        run_id=action.run_id,
    )
