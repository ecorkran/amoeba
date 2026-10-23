"""Which paused Squadron runs Amoeba may offer to prune (slice 110 D8, slice 120 D6).

Pure: no store, no clock, no I/O. The input is the outcome document
``sq runs wait --json`` printed for each owned run, never a run-state file. A run
is a candidate only if **all five** hold, and a null in any of them makes it a
non-candidate (unknown is not a value to guess):

1. Amoeba owns it: its id is in ``owned``, the run ids some project's journal
   adopted or completed.
2. No node that is not ``done`` names it: its id is not in ``held``. This is
   stricter than "no open checkpoint": after a human resolves a checkpoint the
   node is runnable and the Runner has not yet resumed the run, and pruning in
   that window would delete the run it is about to resume.
3. Its ``outcome`` and its ``status`` both say ``paused``.
4. ``checkpoint.paused_at`` is present and timezone-aware: a pause whose
   checkpoint Squadron could not report is never chosen.
5. Its ``updated_at`` is present, timezone-aware, and at least
   :data:`PRUNE_RETENTION` before ``now``. Retention is measured from the run's
   last activity, which is never earlier than ``paused_at``.

Runs the PM launched fail condition 1 and are never touched.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Set
from datetime import datetime, timedelta
from typing import Final

from amoeba.process.sq_outcome import RunOutcome, RunOutcomeDocument

#: How long a paused run must sit untouched before it is offered. The CLI
#: exposes no flag for it; it becomes a setting when something needs to.
PRUNE_RETENTION = timedelta(days=7)

#: The one spelling of the status pruning looks for, derived from the outcome
#: enum so the two cannot drift: Squadron's paused status and paused outcome are
#: the same word, and a run whose document disagrees is not a candidate.
PAUSED_STATUS: Final = RunOutcome.PAUSED.value


def select_prunable(
    documents: Iterable[RunOutcomeDocument],
    *,
    owned: Mapping[str, str],
    held: Set[str],
    now: datetime,
) -> tuple[RunOutcomeDocument, ...]:
    """The documents meeting all five conditions, ordered by run id.

    ``owned`` maps a run id to its owning project. The caller counts the owned
    paused runs that are *not* returned, to report how many were kept.
    """
    return tuple(
        sorted(
            (doc for doc in documents if _is_prunable(doc, owned, held, now)),
            key=lambda doc: doc.run_id,
        )
    )


def _is_prunable(
    document: RunOutcomeDocument,
    owned: Mapping[str, str],
    held: Set[str],
    now: datetime,
) -> bool:
    if document.run_id not in owned or document.run_id in held:
        return False
    if document.outcome is not RunOutcome.PAUSED or document.status != PAUSED_STATUS:
        return False
    paused_at = document.checkpoint.paused_at if document.checkpoint else None
    updated_at = document.updated_at
    if paused_at is None or paused_at.tzinfo is None:
        return False
    # A naive timestamp has no offset to compare against ``now``: unknown.
    if updated_at is None or updated_at.tzinfo is None:
        return False
    return now - updated_at >= PRUNE_RETENTION
