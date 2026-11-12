"""``sweep_scope``: the close sweep for ``status`` (slice 228, D4).

``status`` already makes one ``sq runs list --json --all`` call, so every open row of
a member in scope is judged from that one listing and no ``sq`` call is added. A run
in the listing gives its state or later pause; a run absent from it is gone only when
its run file is absent too (a file check, no subprocess), so an incomplete listing
never closes a live question. The table and the compare-and-set write are
``question_sweep``'s.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

from amoeba.config.user_config import UserConfig
from amoeba.operations.deps import Deps
from amoeba.operations.question_sweep import RunFate, SweepResult, apply_sweep
from amoeba.store.models import QuestionRecord
from amoeba.store.store import Store
from amoeba.store.vocabulary import ClosedReason
from amoeba.upstream.squadron.run_file import run_file_exists
from amoeba.upstream.squadron.run_list import ListedRun

#: ``closed_detail`` for a run neither listed nor on disk.
GONE_DETAIL = "not listed by sq runs list --all, and no run file"


def sweep_scope(  # noqa: PLR0913 - the pieces status already has in hand
    store: Store,
    config: UserConfig,
    rows: Sequence[QuestionRecord],
    listed: Sequence[ListedRun],
    deps: Deps,
    now: datetime,
) -> SweepResult:
    """Close the open ``rows`` whose run, per ``listed``, is not at their pause.

    Raises:
        StoreError: Anything but a busy lock (which is reported as ``problem``).
    """
    runs = {run.run_id: run for run in listed}
    judged: list[tuple[QuestionRecord, RunFate]] = []
    for row in rows:
        fate = _fate(row, runs.get(row.key.run_id), deps.squadron_runs_dir)
        if fate is not None:
            judged.append((row, fate))
    return apply_sweep(store, config, judged, now)


def _fate(row: QuestionRecord, run: ListedRun | None, runs_dir: Path) -> RunFate | None:
    """Where the row's run is now, or ``None`` when the row stays open."""
    if run is None:
        if run_file_exists(runs_dir, row.key.run_id):
            return None  # Squadron still has the run; the listing was incomplete
        return RunFate(ClosedReason.RUN_GONE, GONE_DETAIL, None)
    if not run.is_paused:
        return RunFate(ClosedReason.RUN_MOVED_ON, run.status, None)
    checkpoint = run.checkpoint
    if checkpoint is None or checkpoint.paused_at is None:
        return None  # paused, but not at a pause that can be compared
    if checkpoint.paused_at == row.key.paused_at:
        return None
    return RunFate(ClosedReason.RUN_MOVED_ON, f"paused at {checkpoint.paused_at}", None)
