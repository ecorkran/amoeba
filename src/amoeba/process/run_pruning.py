"""Which paused Squadron runs Amoeba may offer to prune (slice 110, D8).

Pure: no store, no clock, no I/O. A run is a candidate only if **all four** hold:

1. Amoeba owns it: its id is in ``owned``, the run ids some project's journal
   adopted or completed.
2. Its run file says ``paused``.
3. No node that is not ``done`` names it: its id is not in ``held``. This is
   stricter than "no open checkpoint": after a human resolves a checkpoint the
   node is runnable and the Runner has not yet resumed the run, and pruning in
   that window would delete the run it is about to resume.
4. Its ``updated_at`` is at least :data:`PRUNE_RETENTION` before ``now``. A run
   with no ``updated_at`` is never a candidate: unknown is not a value to guess.

Runs the PM launched fail condition 1 and are never touched.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Set
from datetime import datetime, timedelta

from amoeba.process.observers.sq_runs import SquadronRun

#: How long a paused run must sit untouched before it is offered. The CLI
#: exposes no flag for it; it becomes a setting when something needs to.
PRUNE_RETENTION = timedelta(days=7)

#: How long ``sq runs prune`` may take before Amoeba treats it as failed.
SQ_PRUNE_TIMEOUT_SECONDS = 30.0

#: The one spelling of the status pruning looks for.
PAUSED_STATUS = "paused"


def select_prunable(
    runs: Iterable[SquadronRun],
    *,
    owned: Mapping[str, str],
    held: Set[str],
    now: datetime,
) -> tuple[SquadronRun, ...]:
    """The runs meeting all four conditions, ordered by run id.

    ``owned`` maps a run id to its owning project. The caller counts the owned
    paused runs that are *not* returned, to report how many were kept.
    """
    return tuple(
        sorted(
            (run for run in runs if _is_prunable(run, owned, held, now)),
            key=lambda run: run.run_id,
        )
    )


def _is_prunable(
    run: SquadronRun, owned: Mapping[str, str], held: Set[str], now: datetime
) -> bool:
    if run.run_id not in owned or run.run_id in held:
        return False
    if run.status != PAUSED_STATUS or run.updated_at is None:
        return False
    return now - run.updated_at >= PRUNE_RETENTION
