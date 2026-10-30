"""Where a blocked slice stands, for judging its resolution (slice 127, D2; 132, D6).

Pure and entry-only: no I/O, and nothing is read from the block kind. "A run to
resume" comes from the latest ``sq_run`` entry's recorded outcome, so a paused run
whose slice is blocked on a human (after an unknown review, a failed resume or a
rejected resolution) is still a run to resume.
"""

from __future__ import annotations

from collections.abc import Sequence

from amoeba.runner.resolutions.vocabulary import Situation
from amoeba.runner.supervise import run_to_resume
from amoeba.store import JournalEntry


def classify(entries: Sequence[JournalEntry]) -> Situation:
    """The slice's situation from its ``entries``, oldest first.

    An unresolved latest entry means a command is still being carried out, so the
    block cannot be answered yet.
    """
    latest = entries[-1] if entries else None
    if latest is not None and not latest.is_resolved:
        return Situation.UNRESOLVABLE
    if run_to_resume(entries) is not None:
        return Situation.RUN_TO_RESUME
    return Situation.NO_RUN
