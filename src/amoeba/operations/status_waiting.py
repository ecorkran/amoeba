"""The questions waiting on the PM, joined to their runs (slice 224, D4, D8).

Every ``waiting_on_pm`` question of a member in scope is listed, never dropped: the
PM's list of what to answer must not depend on whether the run is still where it was.
A question is joined to its run by ``run_id`` across the whole listing, and says where
the run is now: still at that pause (``next`` is ``answer``), moved on, or not listed.
Claimed and answered questions are not here; they appear as their run's ``pause``.
"""

from __future__ import annotations

from dataclasses import dataclass

from amoeba.operations.status_models import (
    NextAction,
    NextOperation,
    RunState,
    WaitingEntry,
)
from amoeba.store.models import QuestionRecord
from amoeba.upstream.squadron.run_list import ListedRun

__all__ = ["MemberWaiting", "RunState", "waiting_entries"]


@dataclass(frozen=True)
class MemberWaiting:
    """A waiting entry and the member whose question it is."""

    member_id: str
    entry: WaitingEntry


def waiting_entries(
    open_questions: tuple[QuestionRecord, ...], listed: list[ListedRun]
) -> list[MemberWaiting]:
    """One entry per question, in ``open_questions``'s order (oldest first)."""
    runs = {run.run_id: run for run in listed}
    return [
        MemberWaiting(
            question.member_id, _entry(question, runs.get(question.key.run_id))
        )
        for question in open_questions
    ]


def _entry(question: QuestionRecord, run: ListedRun | None) -> WaitingEntry:
    state, detail = _where(question, run)
    next_action = None
    if state is RunState.AT_PAUSE:
        next_action = NextAction(
            operation=NextOperation.ANSWER,
            run_id=question.key.run_id,
            paused_at=question.key.paused_at,
        )
    return WaitingEntry(
        run_id=question.key.run_id,
        paused_at=question.key.paused_at,
        question=question.question,
        slice_label=question.slice_label,
        waiting_reason=question.waiting_reason,
        waiting_detail=question.waiting_detail,
        since=question.claimed_at,
        run_state=state,
        detail=detail,
        next=next_action,
    )


def _where(
    question: QuestionRecord, run: ListedRun | None
) -> tuple[RunState, str | None]:
    if run is None:
        return RunState.NOT_LISTED, None
    checkpoint = run.checkpoint
    if run.is_paused and checkpoint is not None:
        if checkpoint.paused_at == question.key.paused_at:
            return RunState.AT_PAUSE, None
        return (
            RunState.MOVED_ON,
            f"the run is paused at a later pause ({checkpoint.paused_at})",
        )
    return RunState.MOVED_ON, f"the run is {run.status}"
