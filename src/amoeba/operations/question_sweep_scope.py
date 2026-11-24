"""``sweep_scope``: the close sweep for ``status`` (slice 228, D4).

``status`` already holds the ``runs`` document (one ``sq runs list --json --all`` call,
261 D11), so every open row of the calling machine in scope is judged from it and no
``sq`` call is added. A run in the document gives its state or later pause; a run absent
from it, whether the listing missed it or the document was cut, is gone only when the
client found its run file absent too (``absent_runs``, 262 D9), so a cut or incomplete
document never closes a live question. The hub reads no disk. The table and the
compare-and-set write are ``question_judge``'s.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from amoeba.config.user_config import UserConfig
from amoeba.operations.question_judge import RunFate, SweepResult
from amoeba.operations.question_sweep import apply_sweep
from amoeba.operations.runs_document import RunsDocument, RunStanding, standings
from amoeba.store.models import QuestionRecord
from amoeba.store.store import Store
from amoeba.store.vocabulary import ClosedReason

#: ``closed_detail`` for a run neither listed nor on disk.
GONE_DETAIL = "not listed by sq runs list --all, and no run file"


def sweep_scope(
    store: Store,
    config: UserConfig,
    rows: Sequence[QuestionRecord],
    runs: RunsDocument,
    now: datetime,
) -> SweepResult:
    """Close the open ``rows`` whose run, per ``runs``, is not at their pause.

    Raises:
        StoreError: Anything but a busy lock (which is reported as ``problem``).
    """
    standing = standings(runs)
    absent = frozenset(runs.absent_runs)
    judged: list[tuple[QuestionRecord, RunFate]] = []
    for row in rows:
        fate = _fate(row, standing.get(row.key.run_id), row.key.run_id in absent)
        if fate is not None:
            judged.append((row, fate))
    return apply_sweep(store, config, judged, now)


def _fate(row: QuestionRecord, run: RunStanding | None, absent: bool) -> RunFate | None:
    """Where the row's run is now, or ``None`` when the row stays open."""
    if run is None:
        if not absent:
            return None  # Squadron may still have the run; the listing was incomplete
        return RunFate(ClosedReason.RUN_GONE, GONE_DETAIL, None)
    if not run.is_paused:
        return RunFate(ClosedReason.RUN_MOVED_ON, run.status, None)
    if run.paused_at is None:
        return None  # paused, but not at a pause that can be compared
    if run.paused_at == row.key.paused_at:
        return None
    return RunFate(ClosedReason.RUN_MOVED_ON, f"paused at {run.paused_at}", None)
