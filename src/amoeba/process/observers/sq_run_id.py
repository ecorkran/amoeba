"""Recovery of an ``sq_run`` entry by the run id it carries (slice 120).

Since slice 120 an ``sq_run`` is journaled with its Squadron run id, so recovery
asks Squadron about that one run through :func:`~amoeba.process.sq_outcome.poll_run`
instead of matching attributes against Squadron's internal run files.

* Any run state (D3) means the command reached Squadron and is not finished
  from recovery's point of view: the entry is left in flight for its issuer,
  the Runner, to finish by polling. What an orphaned or unknown-status run
  *means* is the Runner's job (122, 125).
* ``not_found`` is the launch grace rule (D4): a launch is detached and may
  still be creating its run, so inside the grace period the observer waits out
  the remainder once and asks again before it concludes ``NotApplied``.
* Entries journaled before 120 carry no run id. :class:`SquadronRunObserver`
  sends them to the unchanged attribute matcher (D5).

Expected failures are answers (``Unknown``), never exceptions.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timedelta
from typing import Final

from amoeba.process.observers.sq_runs import SquadronRunsObserver
from amoeba.process.recovery import (
    InFlight,
    NotApplied,
    Observation,
    Observer,
    Unknown,
)
from amoeba.process.sq_outcome import (
    PollFailure,
    RunOutcome,
    RunOutcomeDocument,
    poll_run,
)
from amoeba.store.journal_models import PARAM_RUN_ID, JournalEntry

#: Outcomes that mean Squadron holds a state for the run, so the command reached
#: it. Defined once, from :class:`RunOutcome`: the two that mean "no usable
#: state" are the exceptions.
STATE_BEARING_OUTCOMES: Final = frozenset(RunOutcome) - {
    RunOutcome.NOT_FOUND,
    RunOutcome.UNREADABLE,
}


class SquadronRunIdObserver:
    """Answers for an ``sq_run`` entry from ``sq runs wait`` on its run id."""

    def __init__(
        self,
        *,
        launch_grace_seconds: float,
        poll_timeout_seconds: float,
        claimed_run_ids: Mapping[str, str] | None,
        now: Callable[[], datetime],
        sleep: Callable[[float], None],
    ) -> None:
        """Build an observer; every argument is required.

        Args:
            launch_grace_seconds: How long after ``issued_at`` a launch may
                still be creating its run.
            poll_timeout_seconds: The bound on each ``sq`` call.
            claimed_run_ids: Run ids already recorded in another entry's
                result, mapped to that entry's id. Such a run is never adopted
                by a second entry.
            now: The clock, injected so tests control it.
            sleep: Waits for the remainder of the grace period, injected so
                tests record it instead of waiting.
        """
        self._grace_seconds = launch_grace_seconds
        self._poll_timeout_seconds = poll_timeout_seconds
        self._claimed_run_ids = dict(claimed_run_ids or {})
        self._now = now
        self._sleep = sleep

    def observe(self, entry: JournalEntry) -> Observation:
        """Report what Squadron shows for the run id this entry carries."""
        run_id = entry.parameters.get(PARAM_RUN_ID)
        if not isinstance(run_id, str) or not run_id:
            return Unknown(
                reason=f"entry {entry.id} has an unusable {PARAM_RUN_ID}: {run_id!r}"
            )
        owner = self._claimed_run_ids.get(run_id)
        if owner is not None and owner != entry.id:
            return Unknown(
                reason=f"run {run_id} is already recorded on entry {owner}",
                candidates=(run_id,),
            )

        answer = _classify(run_id, self._poll(run_id))
        if answer is not None:
            return answer
        return self._not_found(entry, run_id)

    def _poll(self, run_id: str) -> RunOutcomeDocument | PollFailure:
        return poll_run(run_id, timeout_seconds=self._poll_timeout_seconds)

    def _not_found(self, entry: JournalEntry, run_id: str) -> Observation:
        """The launch grace rule (D4): wait out the remainder once, ask again."""
        not_applied = NotApplied(
            f"no run state for {run_id} after the launch grace period"
        )
        if entry.issued_at is None:
            return Unknown(
                reason=f"entry {entry.id} has no issued_at to measure the "
                f"launch grace period from"
            )
        if entry.issued_at.tzinfo is None:
            # A naive timestamp has no offset to compare with the clock: unknown.
            return Unknown(reason=f"entry {entry.id} has a naive issued_at")
        deadline = entry.issued_at + timedelta(seconds=self._grace_seconds)
        remaining = (deadline - self._now()).total_seconds()
        if remaining <= 0:
            return not_applied
        # Capped, so an issued_at ahead of the local clock cannot stretch the wait.
        self._sleep(min(remaining, self._grace_seconds))
        second = _classify(run_id, self._poll(run_id))
        return not_applied if second is None else second


def _classify(
    run_id: str, poll: RunOutcomeDocument | PollFailure
) -> Observation | None:
    """Leave in flight or escalate on a poll; ``None`` means no such run."""
    if isinstance(poll, PollFailure):
        return Unknown(reason=poll.reason)
    if poll.outcome in STATE_BEARING_OUTCOMES:
        return InFlight(run_id=run_id, outcome=poll.outcome)
    if poll.outcome is RunOutcome.UNREADABLE:
        return Unknown(reason=f"the run state for {run_id} is unreadable")
    return None


class SquadronRunObserver:
    """Routes an ``sq_run`` entry: run id present → by id, absent → legacy matcher."""

    def __init__(self, by_id: Observer, legacy: SquadronRunsObserver) -> None:
        self._by_id = by_id
        self._legacy = legacy

    def observe(self, entry: JournalEntry) -> Observation:
        """Dispatch on whether the entry carries a run id."""
        if PARAM_RUN_ID in entry.parameters:
            return self._by_id.observe(entry)
        return self._legacy.observe(entry)
