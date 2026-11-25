"""The questions waiting on the PM, joined to their runs (slice 224, D4, D8).

Every ``waiting_on_pm`` question of a member in scope is listed, never dropped: the
PM's list of what to answer must not depend on whether the run is still where it was.
A question is joined to its run by ``run_id`` across the whole listing, and says where
the run is now: still at that pause (``next`` is ``answer``), moved on, or not listed.
Claimed and answered questions are not here; they appear as their run's ``pause``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from amoeba.answering.values import REQUEST_DECLINE_REASONS
from amoeba.operations.runs_document import RunStanding
from amoeba.operations.status_models import (
    NextAction,
    NextOperation,
    WaitingEntry,
    WaitingRunState,
)
from amoeba.store.machines import MachineCalled
from amoeba.store.models import QuestionRecord
from amoeba.store.row_values import encode_timestamp

__all__ = ["MemberWaiting", "WaitingRunState", "waiting_entries"]


@dataclass(frozen=True)
class MemberWaiting:
    """A waiting entry and the member whose question it is."""

    member_id: str
    entry: WaitingEntry


def waiting_entries(
    open_questions: tuple[QuestionRecord, ...],
    runs: Mapping[str, RunStanding],
    machines: Mapping[int, MachineCalled],
    calling_machine: int,
) -> list[MemberWaiting]:
    """One entry per question, in ``open_questions``'s order (oldest first), each
    naming its machine; one on another machine also says when that machine last
    called the hub (262 D7)."""
    return [
        MemberWaiting(
            question.member_id,
            _entry(
                question,
                runs.get(question.key.run_id),
                _machine(question, machines, calling_machine),
                on_other_machine=question.machine_id not in (None, calling_machine),
            ),
        )
        for question in open_questions
    ]


def _machine(
    question: QuestionRecord,
    machines: Mapping[int, MachineCalled],
    calling_machine: int,
) -> tuple[str | None, str | None]:
    """The question's machine name, and its last call when it is another's."""
    if question.machine_id is None:
        return None, None
    machine = machines[question.machine_id]
    if question.machine_id == calling_machine or machine.last_called_at is None:
        return machine.name, None
    return machine.name, encode_timestamp(machine.last_called_at)


def _entry(
    question: QuestionRecord,
    run: RunStanding | None,
    machine: tuple[str | None, str | None],
    *,
    on_other_machine: bool,
) -> WaitingEntry:
    if on_other_machine:
        # This call cannot say where that run is: only its own machine can (263 D11).
        state, detail = WaitingRunState.OTHER_MACHINE, None
    else:
        state, detail = _where(question, run)
    next_action = None
    if state is WaitingRunState.AT_PAUSE:
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
        request_id=(
            question.request_id
            if question.waiting_reason in REQUEST_DECLINE_REASONS
            else None
        ),
        machine=machine[0],
        machine_last_called_at=machine[1],
    )


def _where(
    question: QuestionRecord, run: RunStanding | None
) -> tuple[WaitingRunState, str | None]:
    if run is None:
        return WaitingRunState.NOT_LISTED, None
    if run.is_paused and run.has_checkpoint:
        if run.paused_at == question.key.paused_at:
            return WaitingRunState.AT_PAUSE, None
        return (
            WaitingRunState.MOVED_ON,
            f"the run is paused at a later pause ({run.paused_at})",
        )
    return WaitingRunState.MOVED_ON, f"the run is {run.status}"
