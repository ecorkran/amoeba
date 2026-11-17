"""The Waking section of the text of ``list`` and ``status`` (slice 244, D9)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from amoeba.cli.render.waiting import NOTHING_NEEDS_YOU, render_waiting
from amoeba.cli.render.waking import WAKING
from amoeba.operations.decisions_models import MemberName
from amoeba.operations.status_models import (
    MemberStatus,
    ProgramStatus,
    StatusOutcome,
    StatusResult,
    WakeLastProblem,
    WakeRunning,
    WakeStatus,
    WakeStopped,
)
from amoeba.store.vocabulary import WakeOutcome

NOW = datetime(2026, 11, 16, 12, 0, tzinfo=UTC)
CORE = MemberName(id="id-core", name="core")
LINT = MemberName(id="id-lint", name="lint")
COMMAND = "wake-agent --max-seconds 60"
STEM = "/state/logs/wake/aaaa"
SECRET_MARKER = "SECRET-MARKER-IN-A-COMMAND"


def _running(*, overdue: bool, pid: int | None = 4242) -> WakeRunning:
    return WakeRunning(
        started_at=NOW - timedelta(minutes=5),
        deadline_at=NOW + timedelta(minutes=25) if not overdue else NOW,
        command_pid=pid,
        log_stem=STEM,
        overdue=overdue,
    )


def _problem(
    outcome: WakeOutcome = WakeOutcome.START_FAILED,
    *,
    exit_code: int | None = None,
    detail: str | None = "FileNotFoundError: No such file or directory",
) -> WakeLastProblem:
    return WakeLastProblem(
        outcome=outcome,
        exit_code=exit_code,
        detail=detail,
        ended_at=NOW - timedelta(hours=3, minutes=2),
        log_stem=STEM,
    )


def _wake(
    *,
    command: str = COMMAND,
    running: WakeRunning | None = None,
    stopped: WakeStopped | None = None,
    last_problem: WakeLastProblem | None = None,
) -> WakeStatus:
    return WakeStatus(
        command=command, running=running, stopped=stopped, last_problem=last_problem
    )


def _text(*members: tuple[MemberName, WakeStatus | None]) -> str:
    statuses = tuple(
        MemberStatus(member=name, runs=(), waiting_on_pm=(), wake=wake)
        for name, wake in members
    )
    result = StatusResult(
        outcome=StatusOutcome.LISTED,
        programs=(ProgramStatus(program="trading", members=statuses),),
    )
    return render_waiting(result, now=NOW)


def _section(text: str) -> list[str]:
    lines = text.splitlines()
    start = lines.index(WAKING)
    end = next(
        (index for index in range(start, len(lines)) if lines[index] == ""),
        len(lines),
    )
    return [line.strip() for line in lines[start + 1 : end]]


def test_the_command_is_on_its_own_line_under_the_member() -> None:
    section = _section(_text((CORE, _wake())))

    assert section == ["core", "wake command:", COMMAND]


def test_a_live_wake_says_how_long_it_has_run_and_when_it_stops() -> None:
    section = _section(_text((CORE, _wake(running=_running(overdue=False)))))

    assert "running since 5m, stops 2026-11-16 12:25" in section


def test_an_overdue_wake_says_no_end_was_recorded_with_the_pid_and_log() -> None:
    section = _section(_text((CORE, _wake(running=_running(overdue=True)))))

    assert (
        "overdue since 2026-11-16 12:00: no end was recorded, so its wrapper is "
        "probably gone; the command's own cap ends it, or check and stop pid 4242, "
        f"log {STEM}"
    ) in section


def test_an_overdue_wake_with_no_pid_has_no_pid_text() -> None:
    section = _section(_text((CORE, _wake(running=_running(overdue=True, pid=None)))))

    (line,) = [entry for entry in section if entry.startswith("overdue")]
    assert "pid" not in line
    assert line.endswith(f"ends it, log {STEM}")


def test_a_stopped_member_says_how_many_wakes_were_used() -> None:
    section = _section(_text((CORE, _wake(stopped=WakeStopped(used=2, limit=2)))))

    assert "waking stopped: 2 of 2 wakes used in the last 24 h" in section


def test_the_last_problem_says_the_outcome_age_reason_and_log() -> None:
    section = _section(_text((CORE, _wake(last_problem=_problem()))))

    assert (
        "last wake start_failed 3h 2m ago: FileNotFoundError: No such file or "
        f"directory, log {STEM}"
    ) in section


def test_a_non_zero_exit_names_its_code() -> None:
    problem = _problem(WakeOutcome.EXITED, exit_code=3, detail=None)

    section = _section(_text((CORE, _wake(last_problem=problem))))

    assert f"last wake exited with code 3 3h 2m ago, log {STEM}" in section


def test_a_member_without_a_command_has_no_lines_and_none_means_no_section() -> None:
    some = _text((CORE, _wake()), (LINT, None))
    none = _text((CORE, None), (LINT, None))

    section = some.split(WAKING, 1)[1]
    assert "core" in section and "lint" not in section
    assert WAKING not in none


def test_waking_leaves_nothing_needs_you_in_place() -> None:
    text = _text((CORE, _wake(running=_running(overdue=False))))

    assert NOTHING_NEEDS_YOU in text


def test_the_secret_like_marker_appears_only_on_the_command_line() -> None:
    wake = _wake(
        command=f"/nonexistent/{SECRET_MARKER}-agent",
        last_problem=_problem(),
    )

    text = _text((CORE, wake))

    assert text.count(SECRET_MARKER) == 1
    (marked,) = [line for line in text.splitlines() if SECRET_MARKER in line]
    assert marked.strip() == f"/nonexistent/{SECRET_MARKER}-agent"
    assert SECRET_MARKER not in "".join(
        line for line in text.splitlines() if line.strip().startswith("last wake")
    )
