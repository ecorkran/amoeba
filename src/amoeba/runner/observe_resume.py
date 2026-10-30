"""Observe a resume that has not yet taken (slice 127, D6).

A resumed run prints no ``run_id=`` line, so there is nothing to wait for: the run
is polled on ``run_poll_interval_seconds`` and judged by :func:`resume_progress`. It
is confirmed when the run leaves the state it was resumed from (a pause, or a
transient failure), and failed on observed state and the tracked child's exit code,
never on message text. A resume the child failed is polled once more before it is
called failed: a run whose owner came back is simply running (D5). This holds whether or
not the child is tracked: after a restart no child is tracked, and the grace rule is
the only one that can fire.

``RunObserver`` delegates here and keeps everything else (polling pace, faults,
ending an entry), which it hands in as callables.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timedelta
from pathlib import Path

from amoeba.process import PollFailure, RunOutcomeDocument, RunPoll
from amoeba.runner.budget import TickBudget
from amoeba.runner.decide import InFlightRun, RunState
from amoeba.runner.faults import ResumeFailure, TickFaults
from amoeba.runner.launch import LaunchTracker, TrackedLaunch, log_paths, stderr_tail
from amoeba.runner.observed import Finished, ObservedRun, ResumeFailed
from amoeba.runner.resolutions.confirm import (
    Confirmed,
    ResumedFrom,
    StillResuming,
    resume_progress,
    resumed_from_entry,
)
from amoeba.runner.resolutions.vocabulary import Continuation
from amoeba.store import PARAM_CONTINUATION, PARAM_CONTINUES, JournalEntry, Store

#: The continuations that resume a run; an ``observe`` continuation does not.
_RESUMING = frozenset({Continuation.RETRY.value, Continuation.ACCEPT.value})

type Classify = Callable[[JournalEntry, str, RunPoll, TickFaults], ObservedRun]
type Ended = Callable[[JournalEntry, str, Finished], ObservedRun]
type RaiseFault = Callable[[JournalEntry, str, str, TickFaults], ObservedRun]


def is_resume(entry: JournalEntry) -> bool:
    """Whether the entry resumes a paused run (``retry`` or ``accept``)."""
    return entry.parameters.get(PARAM_CONTINUATION) in _RESUMING


def resume_pending(entry: JournalEntry, tracked: TrackedLaunch | None) -> bool:
    """Whether the entry is a resume not yet confirmed in memory."""
    return is_resume(entry) and (tracked is None or not tracked.confirmed)


def resumed_from_states(
    store: Store, entries: Sequence[JournalEntry]
) -> dict[str, ResumedFrom | None]:
    """The state each unresolved resume was issued from, by entry id.

    A missing continued entry or an unparseable outcome document maps to ``None``,
    which the confirmation rule treats as "cannot confirm": the resume waits out the
    grace period and fails ``no_claim_within_grace``.
    """
    states: dict[str, ResumedFrom | None] = {}
    for entry in entries:
        if not is_resume(entry):
            continue
        continues = entry.parameters.get(PARAM_CONTINUES)
        continued = (
            store.journal_entry(continues) if isinstance(continues, str) else None
        )
        states[entry.id] = resumed_from_entry(continued)
    return states


class ResumeObserver:
    """Judges one poll of an unconfirmed resume."""

    def __init__(
        self,
        *,
        supervisor_dir: Path,
        tracker: LaunchTracker,
        now: Callable[[], datetime],
        launch_grace_seconds: float,
        poll: Callable[[str], RunPoll],
        classify: Classify,
        ended: Ended,
        fault: RaiseFault,
    ) -> None:
        self._poll = poll
        self._supervisor_dir = supervisor_dir
        self._tracker = tracker
        self._now = now
        self._grace = timedelta(seconds=launch_grace_seconds)
        self._classify = classify
        self._ended = ended
        self._fault = fault

    def step(
        self,
        entry: JournalEntry,
        run_id: str,
        poll: RunPoll,
        resumed_from: Mapping[str, ResumedFrom | None],
        faults: TickFaults,
        budget: TickBudget,
    ) -> ObservedRun:
        """Confirm, keep waiting, or end the entry with a ``ResumeFailed``."""
        if isinstance(poll, PollFailure):
            return self._classify(entry, run_id, poll, faults)
        issued_at = entry.issued_at
        if issued_at is None or issued_at.tzinfo is None:
            reason = "has no timezone-aware issued_at"
            return self._fault(entry, run_id, reason, faults)
        tracked = self._tracker.get(entry.id)
        exit_code = None if tracked is None else tracked.child.poll()
        origin = resumed_from.get(entry.id)
        past_grace = self._now() >= issued_at + self._grace
        progress = resume_progress(poll, origin, exit_code, past_grace)
        if exit_code is not None and isinstance(progress, ResumeFailure):
            # Squadron refuses a resume of a run that is live. That is a poll away
            # from looking failed, so look again before calling it one (D5).
            if progress is not ResumeFailure.RUN_MISSING:
                if not budget.allows_call():
                    return ObservedRun(InFlightRun(entry, run_id, RunState.LAUNCHING))
                poll = self._poll(run_id)
                if isinstance(poll, PollFailure):
                    return self._classify(entry, run_id, poll, faults)
                progress = resume_progress(poll, origin, exit_code, past_grace)
        if isinstance(progress, StillResuming):
            return ObservedRun(InFlightRun(entry, run_id, RunState.LAUNCHING))
        if isinstance(progress, Confirmed):
            if tracked is not None:
                self._tracker.confirm(entry.id)
            return self._classify(entry, run_id, poll, faults)
        return self._ended(
            entry, run_id, self._failed(entry, progress, poll, exit_code)
        )

    def _failed(
        self,
        entry: JournalEntry,
        failure: ResumeFailure,
        poll: RunOutcomeDocument,
        exit_code: int | None,
    ) -> ResumeFailed:
        tail = tail_or_error(log_paths(self._supervisor_dir, entry.id).stderr)
        return ResumeFailed(failure, exit_code, tail, poll)


def tail_or_error(path: Path) -> str:
    """The stderr tail of a launch log, or the error that kept it from being read."""
    try:
        return stderr_tail(path)
    except OSError as error:
        # Expected: the log vanished. The error replaces the tail in the report.
        return f"stderr log unreadable: {error}"


__all__ = [
    "ResumeObserver",
    "is_resume",
    "resume_pending",
    "resumed_from_states",
    "tail_or_error",
]
