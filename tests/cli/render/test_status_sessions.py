"""Live sessions in the text of ``list`` and ``status`` (slice 241, D8, 10.2)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from amoeba.cli.render.sessions import LIVE_SESSIONS, PUSH_CONFIRMED, PUSH_UNCONFIRMED
from amoeba.cli.render.waiting import NOTHING_NEEDS_YOU, render_waiting
from amoeba.operations.decisions_models import MemberName
from amoeba.operations.status_models import (
    MemberStatus,
    ProgramStatus,
    SessionEntry,
    StatusOutcome,
    StatusResult,
)

NOW = datetime(2026, 11, 16, 12, 0, tzinfo=UTC)
CORE = MemberName(id="id-core", name="core")
LINT = MemberName(id="id-lint", name="lint")


def _session(*, confirmed: bool, directory: str = "/work/core") -> SessionEntry:
    return SessionEntry(
        client="claude-code",
        directory=directory,
        started_at=NOW - timedelta(hours=2, minutes=5),
        heartbeat_at=NOW - timedelta(minutes=1),
        push_confirmed_at=NOW - timedelta(minutes=30) if confirmed else None,
    )


def _text(*members: tuple[MemberName, tuple[SessionEntry, ...]]) -> str:
    statuses = tuple(
        MemberStatus(member=name, runs=(), waiting_on_pm=(), sessions=sessions)
        for name, sessions in members
    )
    result = StatusResult(
        outcome=StatusOutcome.LISTED,
        programs=(ProgramStatus(program="trading", members=statuses),),
    )
    return render_waiting(result, now=NOW)


def test_a_session_renders_as_one_line_under_its_member() -> None:
    text = _text((CORE, (_session(confirmed=True),)))

    lines = text.splitlines()
    start = lines.index(LIVE_SESSIONS)
    assert lines[start + 1].strip() == "core"
    assert lines[start + 2].strip() == (
        "claude-code  /work/core  up 2h 5m  last beat 1m ago  push confirmed"
    )


def test_confirmed_and_unconfirmed_render_differently() -> None:
    confirmed = _text((CORE, (_session(confirmed=True),)))
    unconfirmed = _text((CORE, (_session(confirmed=False),)))

    assert confirmed.rstrip().endswith(PUSH_CONFIRMED)
    assert unconfirmed.rstrip().endswith(PUSH_UNCONFIRMED)


def test_a_member_with_no_sessions_has_no_lines_and_none_means_no_section() -> None:
    some = _text((CORE, (_session(confirmed=False),)), (LINT, ()))
    none = _text((CORE, ()), (LINT, ()))

    section = some.split(LIVE_SESSIONS, 1)[1]
    assert "core" in section and "lint" not in section
    assert LIVE_SESSIONS not in none


def test_nothing_needs_you_still_prints_with_only_sessions_present() -> None:
    text = _text((CORE, (_session(confirmed=True),)))

    assert text.splitlines()[0] == NOTHING_NEEDS_YOU
    assert LIVE_SESSIONS in text
