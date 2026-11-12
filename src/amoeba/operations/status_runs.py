"""One ``status`` entry per placed run: pause class and what to do (slice 224, D3, D8).

The class comes from ``classify_pause``, the same function ``handle_pause`` uses, so a
run ``status`` shows as a missed hook is one ``handle_pause`` picks up. ``status`` does
not poll: ``handle_pause``'s poll makes the final call. The run file is read only for a
paused agent question that has no row; a run file that cannot be read is that run's
``run_file_unreadable``, not a failure of the whole call.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from amoeba.operations.pause_class import (
    ObservedPause,
    PauseClass,
    classify_pause,
    run_facts_needed,
)
from amoeba.operations.status_models import (
    CheckpointEntry,
    NextAction,
    NextOperation,
    RunEntry,
    RunFileUnreadable,
)
from amoeba.operations.status_placement import PlacedRun
from amoeba.store.errors import StoreRowError
from amoeba.store.models import AnswerRecord, QuestionRecord
from amoeba.store.vocabulary import QuestionState
from amoeba.upstream.squadron.run_file import RunFacts, RunFileProblem, read_run_facts
from amoeba.upstream.squadron.run_list import ListedCheckpoint, ListedRun
from amoeba.upstream.squadron.run_outcome import UnknownKind, parse_checkpoint_kind

#: The classes ``handle_pause`` acts on: a missed hook, a dead claim, an answer left
#: undelivered.
HANDLED_BY_HANDLE_PAUSE = frozenset(
    {
        PauseClass.UNHANDLED,
        PauseClass.CLAIM_STALE,
        PauseClass.ANSWERED_UNRESUMED,
    }
)

#: Latest question row and its latest answer, by run id (``latest_rows_by_run``).
type LatestRows = Mapping[str, tuple[QuestionRecord, AnswerRecord | None]]

#: What an answer's resume outcome reads as before any attempt.
_NOT_ATTEMPTED = "not attempted"


@dataclass(frozen=True)
class MemberRun:
    """A run entry and the member it belongs under."""

    member_id: str
    entry: RunEntry


def classify_runs(
    placed: tuple[PlacedRun, ...],
    rows: LatestRows,
    runs_dir: Path,
    claim_age_limit: float,
    now: datetime,
) -> list[MemberRun]:
    """One entry per placed run, in the listing's order."""
    return [
        MemberRun(
            item.member.project_id,
            _entry(item.run, rows, runs_dir, claim_age_limit, now),
        )
        for item in placed
    ]


def _entry(
    run: ListedRun,
    rows: LatestRows,
    runs_dir: Path,
    claim_age_limit: float,
    now: datetime,
) -> RunEntry:
    directory = run.working_directory
    if directory is None:
        raise ValueError(f"run {run.run_id} was placed without a directory")
    pause, detail = _pause_of(run, rows, runs_dir, claim_age_limit, now)
    next_action = None
    if isinstance(pause, PauseClass) and pause in HANDLED_BY_HANDLE_PAUSE:
        checkpoint = run.checkpoint
        next_action = NextAction(
            operation=NextOperation.HANDLE_PAUSE,
            run_id=run.run_id,
            paused_at=None if checkpoint is None else checkpoint.paused_at,
            directory=directory,
        )
    return RunEntry(
        run_id=run.run_id,
        pipeline=run.pipeline,
        status=run.status,
        working_directory=directory,
        checkpoint=_checkpoint_entry(run.checkpoint),
        pause=pause,
        detail=detail,
        next=next_action,
    )


def _checkpoint_entry(checkpoint: ListedCheckpoint | None) -> CheckpointEntry | None:
    if checkpoint is None:
        return None
    return CheckpointEntry(
        kind=checkpoint.kind,
        paused_at=checkpoint.paused_at,
        question=checkpoint.question,
    )


def _pause_of(
    run: ListedRun,
    rows: LatestRows,
    runs_dir: Path,
    claim_age_limit: float,
    now: datetime,
) -> tuple[PauseClass | RunFileUnreadable | None, str | None]:
    """The run's pause class and its detail; ``(None, None)`` if not paused."""
    if not run.is_paused:
        return None, None
    checkpoint = run.checkpoint
    observed = ObservedPause(
        paused=True,
        kind=None if checkpoint is None else checkpoint.kind,
        paused_at=None if checkpoint is None else checkpoint.paused_at,
        question=None if checkpoint is None else checkpoint.question,
    )
    row, answer = _row_for_pause(rows, run.run_id, observed)
    facts: RunFacts | None = None
    if run_facts_needed(observed, row):
        read = read_run_facts(runs_dir, run.run_id)
        if isinstance(read, RunFileProblem):
            return RunFileUnreadable.RUN_FILE_UNREADABLE, read.reason
        facts = read
    pause_class = classify_pause(observed, row, answer, facts, claim_age_limit, now)
    return pause_class, _detail(pause_class, observed, answer)


def _row_for_pause(
    rows: LatestRows, run_id: str, observed: ObservedPause
) -> tuple[QuestionRecord | None, AnswerRecord | None]:
    """The row recorded for this very pause. A run's latest row may belong to an
    earlier pause of it, which says nothing about the pause it is at now."""
    found = rows.get(run_id)
    if found is None or found[0].key.paused_at != observed.paused_at:
        return None, None
    row, answer = found
    if row.state is QuestionState.ANSWERED and answer is None:
        raise StoreRowError(f"question {row.key} is answered but has no answer row")
    return found


def _detail(
    pause_class: PauseClass, observed: ObservedPause, answer: AnswerRecord | None
) -> str | None:
    match pause_class:
        case PauseClass.OTHER_CHECKPOINT:
            return _kind_text(observed.kind)
        case PauseClass.NO_QUESTION_TEXT:
            missing = "paused_at" if observed.paused_at is None else "question text"
            return f"the checkpoint has no {missing}"
        case PauseClass.ANSWERED_UNRESUMED | PauseClass.SETTLED:
            return _resume_text(answer)
        case _:
            return None


def _kind_text(raw: str | None) -> str:
    kind = parse_checkpoint_kind(raw)
    if kind is None:
        return "the listing gives no checkpoint kind"
    shown = kind.raw if isinstance(kind, UnknownKind) else kind.value
    return f"checkpoint kind {shown}"


def _resume_text(answer: AnswerRecord | None) -> str:
    if answer is None:
        raise StoreRowError("an answered question has no latest answer")
    outcome = _NOT_ATTEMPTED if answer.resume_outcome is None else answer.resume_outcome
    if answer.resume_detail:
        return f"{outcome}: {answer.resume_detail}"
    return str(outcome)
