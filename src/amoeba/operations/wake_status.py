"""Waking, as ``status`` and ``list`` show it for a member with a wake command
(slice 244, D9).

One ``wake_summary`` read per member in scope: the unended row (live, or past its
deadline and so overdue), whether the limit of the last 24 hours is reached, and the
newest ended row when it went wrong. Nothing here looks at a process: it is rows and
the clock only.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime

from amoeba.operations.status_models import (
    WakeLastProblem,
    WakeRunning,
    WakeStatus,
    WakeStopped,
)
from amoeba.store.models import Member, Wake
from amoeba.store.store import Store
from amoeba.store.vocabulary import WakeOutcome
from amoeba.store.wakes import WakeSummary, wake_command_of, wake_summary


def read_member_wakes(
    store: Store,
    members: Mapping[str, Member],
    now: datetime,
    max_wakes_per_day: int,
) -> dict[str, WakeStatus]:
    """The ``WakeStatus`` of each member that has a wake command; others are absent."""
    with store.read() as transaction:
        return {
            project_id: build_wake_status(
                command,
                wake_summary(transaction, project_id, now),
                max_wakes_per_day,
            )
            for project_id in members
            if (command := wake_command_of(transaction, project_id)) is not None
        }


def build_wake_status(
    command: str, summary: WakeSummary, max_wakes_per_day: int
) -> WakeStatus:
    """The display of one member's wakes from its summary."""
    return WakeStatus(
        command=command,
        running=_running(summary),
        stopped=(
            WakeStopped(used=summary.used_in_window, limit=max_wakes_per_day)
            if summary.used_in_window >= max_wakes_per_day
            else None
        ),
        last_problem=_last_problem(summary.newest_ended),
    )


def _running(summary: WakeSummary) -> WakeRunning | None:
    wake = summary.unended
    if wake is None:
        return None
    return WakeRunning(
        started_at=wake.started_at,
        deadline_at=wake.deadline_at,
        command_pid=wake.command_pid,
        log_stem=wake.log_stem,
        overdue=summary.overdue,
    )


def _went_wrong(wake: Wake) -> bool:
    """A wake that did not end well: it failed to start, timed out, hit a wrapper
    error, or its command exited with a non-zero code."""
    if wake.outcome is WakeOutcome.EXITED:
        return wake.exit_code != 0
    return wake.outcome is not None


def _last_problem(newest_ended: Wake | None) -> WakeLastProblem | None:
    """The newest ended row decides: a clean exit after an older failure clears it."""
    if newest_ended is None or not _went_wrong(newest_ended):
        return None
    if newest_ended.outcome is None or newest_ended.ended_at is None:
        raise AssertionError("an ended wake has an outcome and an end time")
    return WakeLastProblem(
        outcome=newest_ended.outcome,
        exit_code=newest_ended.exit_code,
        detail=newest_ended.detail,
        ended_at=newest_ended.ended_at,
        log_stem=newest_ended.log_stem,
    )
