"""The **Waking** section of ``status`` and ``list`` (slice 244, D9).

Under each member that has a wake command: the command (plain text, on its own line),
what is running, why waking is stopped, and the last wake that went wrong.
Waking is not other agents' text and waits on nobody: it sets no notice and does not
change ``Nothing needs you.`` No line is cut: a log path is for copying, and a detail
is only an exception class and its OS message.
"""

from __future__ import annotations

from datetime import datetime
from typing import Final

from amoeba.cli.render.text import command_line, how_long, indented
from amoeba.operations.status_models import (
    MemberStatus,
    WakeLastProblem,
    WakeRunning,
    WakeStatus,
    WakeStopped,
)
from amoeba.store.vocabulary import WakeOutcome
from amoeba.store.wakes import WAKE_WINDOW

WAKING: Final = "Waking"
#: How a time is shown in a line.
TIME_FORMAT: Final = "%Y-%m-%d %H:%M"
SECONDS_PER_HOUR: Final = 3600
#: The limit's window in whole hours, from the one definition in the store.
WINDOW_HOURS: Final = int(WAKE_WINDOW.total_seconds() // SECONDS_PER_HOUR)


def waking_section(members: list[MemberStatus], now: datetime) -> list[str]:
    """The section, or nothing when no member has a wake command."""
    lines: list[str] = []
    for member in members:
        if member.wake is None:
            continue
        lines.append(indented(member.member.name))
        lines.extend(_member_lines(member.wake, now))
    return [WAKING, *lines] if lines else []


def _member_lines(wake: WakeStatus, now: datetime) -> list[str]:
    lines = [indented("wake command:", 2), command_line(wake.command, depth=3)]
    if wake.running is not None:
        lines.append(indented(_running_text(wake.running, now), 2))
    if wake.stopped is not None:
        lines.append(indented(_stopped_text(wake.stopped), 2))
    if wake.last_problem is not None:
        lines.append(indented(_last_problem_text(wake.last_problem, now), 2))
    return lines


def _running_text(running: WakeRunning, now: datetime) -> str:
    if not running.overdue:
        return (
            f"running since {how_long(running.started_at, now)}, "
            f"stops {running.deadline_at.strftime(TIME_FORMAT)}"
        )
    stop = (
        ""
        if running.command_pid is None
        else f", or check and stop pid {running.command_pid}"
    )
    log = "" if running.log_stem is None else f", log {running.log_stem}"
    return (
        f"overdue since {running.deadline_at.strftime(TIME_FORMAT)}: no end was "
        f"recorded, so its wrapper is probably gone; the command's own cap ends "
        f"it{stop}{log}"
    )


def _stopped_text(stopped: WakeStopped) -> str:
    return (
        f"waking stopped: {stopped.used} of {stopped.limit} wakes used in the last "
        f"{WINDOW_HOURS} h"
    )


def _outcome_text(problem: WakeLastProblem) -> str:
    if problem.outcome is WakeOutcome.EXITED:
        return f"{problem.outcome.value} with code {problem.exit_code}"
    return problem.outcome.value


def _last_problem_text(problem: WakeLastProblem, now: datetime) -> str:
    text = f"last wake {_outcome_text(problem)} {how_long(problem.ended_at, now)} ago"
    if problem.detail:
        text += f": {problem.detail}"
    if problem.log_stem is not None:
        text += f", log {problem.log_stem}"
    return text
