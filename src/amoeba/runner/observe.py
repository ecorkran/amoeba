"""Observe the project's in-flight runs: confirm launches, poll, classify (D6, D10).

An in-flight run is an unresolved ``sq_run`` entry. A launch made in this process
lifetime is *unconfirmed* until its stderr shows the exact ``run_id=<id>`` line or
a poll finds a state. Any other entry (including one left by a crash) is treated
as confirmed and only polled. Expected failures are recorded in the tick's
:class:`~amoeba.runner.faults.TickFaults`; nothing here raises for them.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import datetime, timedelta
from pathlib import Path

from amoeba.process import PollFailure, RunOutcome, RunPoll
from amoeba.runner.budget import TickBudget, TickResult
from amoeba.runner.decide import InFlightRun, RunState
from amoeba.runner.faults import (
    Fault,
    FaultKind,
    LaunchFailure,
    NodeContext,
    TickFaults,
)
from amoeba.runner.launch import (
    LaunchTracker,
    TrackedLaunch,
    log_paths,
    stderr_confirms,
    stderr_tail,
)
from amoeba.runner.observed import (
    Finished,
    LaunchFailed,
    Observed,
    ObservedRun,
    RunEnded,
    RunVanished,
)
from amoeba.store import PARAM_RUN_ID, JournalEntry

#: The exit code of a child that rejected its command line.
USAGE_ERROR_EXIT_CODE = 2

#: Outcomes of a poll that end the run.
_ENDED = frozenset(
    {
        RunOutcome.COMPLETED,
        RunOutcome.FAILED,
        RunOutcome.PAUSED,
        RunOutcome.ORPHANED,
    }
)


class RunObserver:
    """Observes in-flight runs, keeping last-poll times and overdue launches."""

    def __init__(
        self,
        *,
        supervisor_dir: Path,
        tracker: LaunchTracker,
        poll: Callable[[str], RunPoll],
        now: Callable[[], datetime],
        monotonic: Callable[[], float],
        launch_grace_seconds: float,
        run_poll_interval_seconds: float,
    ) -> None:
        """Build an observer; every argument is required.

        Args:
            supervisor_dir: Holds ``launch-logs/``.
            tracker: The children launched in this lifetime.
            poll: One bounded ``sq runs wait`` for a run id.
            now: Wall clock, to measure the launch grace period from ``issued_at``.
            monotonic: Monotonic clock, for the poll interval.
            launch_grace_seconds: How long after ``issued_at`` a run may still
                be appearing.
            run_poll_interval_seconds: The least time between two polls of a run.
        """
        self._supervisor_dir = supervisor_dir
        self._tracker = tracker
        self._poll = poll
        self._now = now
        self._monotonic = monotonic
        self._grace = timedelta(seconds=launch_grace_seconds)
        self._interval = run_poll_interval_seconds
        self._last_poll: dict[str, float] = {}
        self._overdue: set[str] = set()
        # The last poll-fault per entry, replayed on ticks between polls so a
        # fault that stands does not look recovered (and its escalation close).
        self._faulted: dict[str, Fault] = {}

    def observe(
        self,
        entries: Sequence[JournalEntry],
        budget: TickBudget,
        faults: TickFaults,
        context: NodeContext,
    ) -> Observed:
        """Observe each entry, least recently polled first.

        Sets ``context`` to each entry's node before observing it. Stops with
        ``CUT_OFF`` as soon as a poll is due but the budget refuses.
        """
        ordered = sorted(
            entries, key=lambda e: self._last_poll.get(e.id, float("-inf"))
        )
        runs: list[ObservedRun] = []
        for entry in ordered:
            context.set(entry.node_id)
            observed = self._observe_one(entry, budget, faults)
            if observed is None:
                return Observed(tuple(runs), TickResult.CUT_OFF)
            runs.append(observed)
        return Observed(tuple(runs), TickResult.COMPLETE)

    def _observe_one(
        self, entry: JournalEntry, budget: TickBudget, faults: TickFaults
    ) -> ObservedRun | None:
        run_id = entry.parameters.get(PARAM_RUN_ID)
        if not isinstance(run_id, str) or not run_id:
            # As in recovery, a malformed run id is an answer, not a bug: it
            # faults this entry and the others are still observed.
            return self._fault(entry, "", f"has an unusable run id: {run_id!r}", faults)
        tracked = self._tracker.get(entry.id)
        if tracked is None or tracked.confirmed:
            return self._confirmed(entry, run_id, budget, faults)
        return self._unconfirmed(entry, run_id, tracked, budget, faults)

    # -- a confirmed run ------------------------------------------------------

    def _confirmed(
        self, entry: JournalEntry, run_id: str, budget: TickBudget, faults: TickFaults
    ) -> ObservedRun | None:
        if not self._poll_due(entry.id):
            standing = self._faulted.get(entry.id)
            if standing is None:
                return self._running(entry, run_id)
            faults.add(standing)
            return ObservedRun(InFlightRun(entry, run_id, RunState.FAULT))
        if not budget.allows_call():
            return None
        return self._classify(entry, run_id, self._poll_now(entry.id, run_id), faults)

    def _classify(
        self,
        entry: JournalEntry,
        run_id: str,
        poll: RunPoll,
        faults: TickFaults,
    ) -> ObservedRun:
        """Turn a poll of a confirmed run into running, finished or fault."""
        if isinstance(poll, PollFailure):
            return self._fault(entry, run_id, poll.reason, faults)
        if poll.outcome in _ENDED:
            return self._ended(entry, run_id, RunEnded(poll))
        if poll.outcome is RunOutcome.NOT_FOUND:
            return self._ended(entry, run_id, RunVanished())
        if poll.outcome is RunOutcome.TIMED_OUT:
            return self._running(entry, run_id)
        reason = f"run {run_id} reported {poll.outcome.value}"
        return self._fault(entry, run_id, reason, faults)

    # -- a launch not yet confirmed -------------------------------------------

    def _unconfirmed(
        self,
        entry: JournalEntry,
        run_id: str,
        tracked: TrackedLaunch,
        budget: TickBudget,
        faults: TickFaults,
    ) -> ObservedRun | None:
        stderr_path = log_paths(self._supervisor_dir, entry.id).stderr
        log_error = self._check_line(entry, run_id, stderr_path, tracked, faults)
        if tracked.confirmed:
            return self._running(entry, run_id)
        issued_at = entry.issued_at
        if issued_at is None or issued_at.tzinfo is None:
            # Like a malformed run id: it faults this entry, not the whole tick.
            reason = "has no timezone-aware issued_at"
            return self._fault(entry, run_id, reason, faults)
        exit_code = tracked.child.poll()
        if exit_code is None and self._within_grace(issued_at):
            return self._launching(entry, run_id)
        if not self._poll_due(entry.id):
            return self._still_overdue(entry, run_id, stderr_path, log_error, faults)
        if not budget.allows_call():
            return None
        poll = self._poll_now(entry.id, run_id)
        return self._after_launch_poll(
            entry, run_id, poll, exit_code, stderr_path, log_error, faults
        )

    def _check_line(
        self,
        entry: JournalEntry,
        run_id: str,
        stderr_path: Path,
        tracked: TrackedLaunch,
        faults: TickFaults,
    ) -> str | None:
        """Confirm on the exact line. Returns the log error, if it was unreadable."""
        try:
            confirmed = stderr_confirms(stderr_path, run_id)
        except OSError as error:
            # An expected external failure: answer "no line" this tick and let
            # the run state decide, recording the error for the operator.
            text = f"stderr log unreadable: {error}"
            faults.add(
                Fault(
                    FaultKind.RUN_OBSERVATION_FAILED,
                    f"entry {entry.id}: {text}",
                    node_id=entry.node_id,
                    run_id=run_id,
                )
            )
            return text
        if confirmed:
            self._confirm(entry.id, tracked)
        return None

    def _after_launch_poll(
        self,
        entry: JournalEntry,
        run_id: str,
        poll: RunPoll,
        exit_code: int | None,
        stderr_path: Path,
        log_error: str | None,
        faults: TickFaults,
    ) -> ObservedRun:
        if isinstance(poll, PollFailure):
            return self._fault(entry, run_id, poll.reason, faults)
        if poll.outcome is not RunOutcome.NOT_FOUND:
            tracked = self._tracker.get(entry.id)
            if tracked is not None:
                self._confirm(entry.id, tracked)
            return self._classify(entry, run_id, poll, faults)
        if exit_code is None:
            self._overdue.add(entry.id)
            return self._still_overdue(entry, run_id, stderr_path, log_error, faults)
        failure = (
            LaunchFailure.USAGE_ERROR
            if exit_code == USAGE_ERROR_EXIT_CODE
            else LaunchFailure.EXITED_BEFORE_LINE
        )
        tail = log_error or _tail_or_error(stderr_path)
        return self._ended(entry, run_id, LaunchFailed(failure, exit_code, tail))

    def _still_overdue(
        self,
        entry: JournalEntry,
        run_id: str,
        stderr_path: Path,
        log_error: str | None,
        faults: TickFaults,
    ) -> ObservedRun:
        """Past grace, no line, a poll found no state: raise it, keep the entry."""
        if entry.id in self._overdue:
            tail = log_error or _tail_or_error(stderr_path)
            faults.add(
                Fault(
                    FaultKind.LAUNCH_OVERDUE,
                    f"entry {entry.id}: launch of {run_id} is past its grace "
                    f"period with no run state; stderr: {tail}",
                    node_id=entry.node_id,
                    run_id=run_id,
                )
            )
        return self._launching(entry, run_id)

    # -- helpers ---------------------------------------------------------------

    def _confirm(self, entry_id: str, tracked: TrackedLaunch) -> None:
        tracked.confirmed = True
        self._overdue.discard(entry_id)

    def _poll_due(self, entry_id: str) -> bool:
        last = self._last_poll.get(entry_id)
        return last is None or self._monotonic() - last >= self._interval

    def _poll_now(self, entry_id: str, run_id: str) -> RunPoll:
        self._last_poll[entry_id] = self._monotonic()
        return self._poll(run_id)

    def _within_grace(self, issued_at: datetime) -> bool:
        return self._now() < issued_at + self._grace

    def _launching(self, entry: JournalEntry, run_id: str) -> ObservedRun:
        return ObservedRun(InFlightRun(entry, run_id, RunState.LAUNCHING))

    def _running(self, entry: JournalEntry, run_id: str) -> ObservedRun:
        self._faulted.pop(entry.id, None)
        return ObservedRun(InFlightRun(entry, run_id, RunState.RUNNING))

    def _ended(
        self, entry: JournalEntry, run_id: str, finished: Finished
    ) -> ObservedRun:
        # The observer is shared by every project, so per-entry state is dropped
        # here, when the entry's run ends, and never by pruning to one project.
        self._last_poll.pop(entry.id, None)
        self._overdue.discard(entry.id)
        self._faulted.pop(entry.id, None)
        return ObservedRun(InFlightRun(entry, run_id, RunState.FINISHED), finished)

    def _fault(
        self, entry: JournalEntry, run_id: str, reason: str, faults: TickFaults
    ) -> ObservedRun:
        fault = Fault(
            FaultKind.RUN_OBSERVATION_FAILED,
            f"entry {entry.id}: {reason}",
            node_id=entry.node_id,
            run_id=run_id,
        )
        faults.add(fault)
        self._faulted[entry.id] = fault
        return ObservedRun(InFlightRun(entry, run_id, RunState.FAULT))


def _tail_or_error(path: Path) -> str:
    try:
        return stderr_tail(path)
    except OSError as error:
        # Expected: the log vanished. The error replaces the tail in the report.
        return f"stderr log unreadable: {error}"
