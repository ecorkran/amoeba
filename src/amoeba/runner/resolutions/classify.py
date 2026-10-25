"""Where a blocked step stands, for judging its resolution (slice 127, D2).

Pure and entry-only: no I/O, and nothing is read from the block kind. "Paused" and
"completed" come from the latest ``sq_run`` entry's recorded outcome, so a paused
run whose step is blocked on a human (after an unknown review, a failed resume or a
rejected resolution) is still a paused run.
"""

from __future__ import annotations

from collections.abc import Sequence

from amoeba.process import RunOutcome
from amoeba.runner.finish import RESULT_RESUME_FAILURE
from amoeba.runner.ingest.record import RESULT_OUTCOME
from amoeba.runner.lifecycle.steps import Executor
from amoeba.runner.resolutions.vocabulary import Situation
from amoeba.store import CommandKind, JournalEntry


def classify(executor: Executor | None, entries: Sequence[JournalEntry]) -> Situation:
    """The step's situation from its executor and its ``entries``, oldest first.

    ``executor`` is ``None`` for a node that is not a lifecycle step. Rows are
    tested in D2's order and the first match wins, so an unrouted pause is never
    ``paused_run`` and a failed resume, whose recorded outcome stays ``paused``,
    always is.
    """
    latest_run = next(
        (entry for entry in reversed(entries) if entry.kind is CommandKind.SQ_RUN),
        None,
    )
    latest = entries[-1] if entries else None
    if (latest is not None and not latest.is_resolved) or (
        latest_run is not None and latest_run.awaits_routing
    ):
        return Situation.UNRESOLVABLE
    if executor is None or executor is Executor.HUMAN:
        return Situation.NO_DECISION
    if latest is None or latest.kind is not CommandKind.SQ_RUN:
        return Situation.BEFORE_RUN
    result = latest.result or {}
    outcome = result.get(RESULT_OUTCOME)
    if outcome == RunOutcome.PAUSED.value:
        return Situation.PAUSED_RUN
    if outcome == RunOutcome.COMPLETED.value and RESULT_RESUME_FAILURE not in result:
        return Situation.COMPLETED_OUTCOME
    return Situation.ENDED_RUN
