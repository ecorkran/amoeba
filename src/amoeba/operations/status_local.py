"""The parts of ``status`` that run only on the machine that ran ``sq``, and the
sentences its result adds (slice 261, D11): the close sweep and the pruning of scratch
and logs, which the hub does not run, and the ``file_problems`` and sweep-problem text.
Split from ``status`` to keep it under its size."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime

from amoeba.config.user_config import UserConfig
from amoeba.operations.deps import Deps
from amoeba.operations.prune_models import PruneReport
from amoeba.operations.question_sweep import SweepResult
from amoeba.operations.question_sweep_scope import sweep_scope
from amoeba.operations.runs_document import RunsDocument, RunStanding, left_out_text
from amoeba.store.models import QuestionRecord
from amoeba.store.store import Store


def sweep_if_local(  # noqa: PLR0913 - the pieces status already has in hand
    store: Store,
    config: UserConfig,
    candidates: Sequence[QuestionRecord],
    standing: Mapping[str, RunStanding],
    local: Deps | None,
    now: datetime,
) -> SweepResult:
    if local is None:
        return SweepResult()
    return sweep_scope(
        store, config, candidates, standing, local.squadron_runs_dir, now
    )


def prune_if_local(
    store: Store, config: UserConfig, local: Deps | None, now: datetime
) -> PruneReport:
    if local is None:
        return PruneReport(removed=0, problems=())
    return local.prune(store, now=now, after_days=config.prune_after_days)


def file_problems(
    runs: RunsDocument, call_problems: tuple[str, ...], prune_problems: tuple[str, ...]
) -> tuple[str, ...]:
    """The call-log and prune problems, and the sentence for a cut document."""
    cut = left_out_text(runs.left_out)
    return (*call_problems, *(() if cut is None else (cut,)), *prune_problems)


def joined(*problems: str | None) -> str | None:
    """The sweep problems that happened, one text, or ``None`` when none did."""
    found = [problem for problem in problems if problem is not None]
    return "; ".join(found) if found else None
