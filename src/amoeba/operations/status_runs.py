"""One ``status`` entry per placed run: pause class and what to do (slice 224, D3, D8).

The class comes from ``classify_pause``, the same function ``handle_pause`` uses, so a
run ``status`` shows as a missed hook is one ``handle_pause`` picks up. ``status`` does
not poll: ``handle_pause``'s poll makes the final call. The run file's facts come from
the ``runs`` document, which holds them for every paused run, and are used only for a
paused agent question that has no row; a run file the document says could not be read
is that run's ``run_file_unreadable``, not a failure of the whole call.
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
from amoeba.operations.runs_document import OpenRun, RunCheckpoint
from amoeba.operations.status_models import (
    CheckpointEntry,
    NextAction,
    NextOperation,
    RunEntry,
    RunFileUnreadable,
)
from amoeba.operations.status_placement import PlacedRun
from amoeba.store.errors import StoreRowError
from amoeba.store.messages import effective_state, get_message
from amoeba.store.models import AnswerRecord, QuestionRecord
from amoeba.store.store import Transaction
from amoeba.store.vocabulary import QuestionState, RequestState
from amoeba.upstream.squadron.run_file import ExecutionMode, RunFacts
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

#: The effective state of each held question's request, by request id; ``None`` when
#: the store no longer holds it (242 D9).
type RequestStates = Mapping[str, RequestState | None]

#: What an answer's resume outcome reads as before any attempt.
_NOT_ATTEMPTED = "not attempted"
#: How a held question's request reads when the store no longer holds it.
_REQUEST_GONE = "gone"


@dataclass(frozen=True)
class MemberRun:
    """A run entry and the member it belongs under."""

    member_id: str
    entry: RunEntry


def held_request_states(
    transaction: Transaction, rows: LatestRows, now: datetime
) -> dict[str, RequestState | None]:
    """The effective state of the request of each held row in ``rows``.

    Raises:
        StoreRowError: A held row has no ``request_id``, or names a note.
    """
    states: dict[str, RequestState | None] = {}
    for row, _answer in rows.values():
        if row.state is not QuestionState.WAITING_ON_REQUEST:
            continue
        if row.request_id is None:
            raise StoreRowError(f"held question {row.key} has no request_id")
        message = get_message(transaction, row.request_id)
        if message is None:
            states[row.request_id] = None
            continue
        state = effective_state(message, now)
        states[row.request_id] = state
    return states


def classify_runs(
    placed: tuple[PlacedRun, ...],
    rows: LatestRows,
    requests: RequestStates,
    claim_age_limit: float,
    now: datetime,
) -> list[MemberRun]:
    """One entry per placed run, in the document's order."""
    return [
        MemberRun(
            item.member.project_id,
            _entry(item.run, rows, requests, claim_age_limit, now),
        )
        for item in placed
    ]


def _entry(
    run: OpenRun,
    rows: LatestRows,
    requests: RequestStates,
    claim_age_limit: float,
    now: datetime,
) -> RunEntry:
    if run.working_directory is None:
        raise ValueError(f"run {run.run_id} was placed without a directory")
    directory = Path(run.working_directory)
    pause, detail = _pause_of(run, rows, requests, claim_age_limit, now)
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


def _checkpoint_entry(checkpoint: RunCheckpoint | None) -> CheckpointEntry | None:
    if checkpoint is None:
        return None
    return CheckpointEntry(
        kind=checkpoint.kind,
        paused_at=checkpoint.paused_at,
        question=checkpoint.question,
    )


def _pause_of(
    run: OpenRun,
    rows: LatestRows,
    requests: RequestStates,
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
        read = _facts_of(run)
        if isinstance(read, str):
            return RunFileUnreadable.RUN_FILE_UNREADABLE, read
        facts = read
    pause_class = classify_pause(observed, row, answer, facts, claim_age_limit, now)
    return pause_class, _detail(pause_class, observed, answer, row, requests)


def _facts_of(run: OpenRun) -> RunFacts | str:
    """The run file's facts from the document, or the text saying why there are none."""
    if run.run_file_problem is not None:
        return run.run_file_problem
    if run.run_file is None:
        raise ValueError(
            f"paused run {run.run_id} came with no run file facts or problem"
        )
    try:
        mode = ExecutionMode(run.run_file.execution_mode)
    except ValueError:
        # A mode this code has no name for is that run's unreadable run file.
        shown = run.run_file.execution_mode
        return f"run file of {run.run_id} has execution mode {shown!r}"
    directory = run.run_file.working_directory
    return RunFacts(
        params=dict(run.run_file.params),
        execution_mode=mode,
        working_directory=None if directory is None else Path(directory),
    )


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
    pause_class: PauseClass,
    observed: ObservedPause,
    answer: AnswerRecord | None,
    row: QuestionRecord | None,
    requests: RequestStates,
) -> str | None:
    match pause_class:
        case PauseClass.OTHER_CHECKPOINT:
            return _kind_text(observed.kind)
        case PauseClass.NO_QUESTION_TEXT:
            missing = "paused_at" if observed.paused_at is None else "question text"
            return f"the checkpoint has no {missing}"
        case PauseClass.ANSWERED_UNRESUMED | PauseClass.SETTLED:
            return _resume_text(answer)
        case PauseClass.CLOSED:
            return _closed_text(row)
        case PauseClass.WAITING_ON_REQUEST:
            return _held_text(row, requests)
        case _:
            return None


def _closed_text(row: QuestionRecord | None) -> str:
    if row is None or row.closed_reason is None:
        raise StoreRowError("a closed question has no closed_reason")
    detail = f": {row.closed_detail}" if row.closed_detail else ""
    return (
        f"closed ({row.closed_reason}{detail}). The run is still paused in Squadron; "
        "Amoeba does not resume or end it. `sq run --resume` continues it"
    )


def _held_text(row: QuestionRecord | None, requests: RequestStates) -> str:
    """``waiting on request <id> (<state>)``, and when ``start_ended_held`` last
    started ``handle_pause`` for it (242 D9)."""
    if row is None or row.request_id is None:
        raise StoreRowError("a held question has no request_id")
    if row.request_id not in requests:
        raise StoreRowError(f"request {row.request_id} of a held question was not read")
    state = requests[row.request_id]
    shown = _REQUEST_GONE if state is None else state.value
    text = f"waiting on request {row.request_id} ({shown})"
    if row.start_attempted_at is None:
        return text
    return f"{text}; handle_pause last started {row.start_attempted_at.isoformat()}"


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
