"""The Runs on other machines and Behind the hub sections, the session line's machine
and ``behind``, and a question on another machine (slice 263, 7.3, D12)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from amoeba.cli.render.waiting import render_waiting
from amoeba.operations.decisions_models import MemberName
from amoeba.operations.runs_document import RunCheckpoint
from amoeba.operations.status_machine_models import MachineEntry, MachineRunLine
from amoeba.operations.status_models import (
    MemberStatus,
    ProgramStatus,
    SessionEntry,
    StatusOutcome,
    StatusResult,
    WaitingEntry,
    WaitingRunState,
)

NOW = datetime(2026, 11, 24, 12, 0, tzinfo=UTC)
HUB = 3
CORE = MemberName(id="id-core", name="core")


def _machine(name: str, **fields: object) -> MachineEntry:
    base: dict[str, object] = {
        "name": name,
        "last_called_at": NOW,
        "client_version": "0.2.3",
        "door_version": HUB,
        "behind": False,
    }
    return MachineEntry.model_validate({**base, **fields})


def _session(*, door: int = HUB, behind: bool = False) -> SessionEntry:
    return SessionEntry(
        client="claude-code",
        machine="beta",
        client_version="0.2.0",
        door_version=door,
        behind=behind,
        directory="/work/core",
        started_at=NOW - timedelta(hours=1),
        heartbeat_at=NOW - timedelta(minutes=1),
        push_confirmed_at=None,
    )


def _text(
    machines: tuple[MachineEntry, ...],
    sessions: tuple[SessionEntry, ...] = (),
    waiting: tuple[WaitingEntry, ...] = (),
) -> str:
    member = MemberStatus(
        member=CORE, runs=(), waiting_on_pm=waiting, sessions=sessions
    )
    result = StatusResult(
        outcome=StatusOutcome.LISTED,
        programs=(ProgramStatus(program="trading", members=(member,)),),
        hub_door_version=HUB,
        machines=machines,
    )
    return render_waiting(result, now=NOW)


def _run() -> MachineRunLine:
    return MachineRunLine(
        run_id="run-a1",
        pipeline="p6",
        status="paused",
        directory="/work/alpha",
        checkpoint=RunCheckpoint(kind="gate", paused_at="t", question="q"),
    )


def test_each_heading_form_and_the_run_line() -> None:
    reported = NOW - timedelta(minutes=5)
    text = _text(
        (
            _machine("beta", calling=True),
            _machine("alpha", runs_reported_at=reported, runs=(_run(),)),
            _machine("gamma"),
            _machine("delta", runs_reported_at=reported, runs_problem="bad"),
        )
    )

    assert "Runs on other machines" in text
    assert "alpha, reported 5m ago" in text
    assert "run-a1  p6  paused  /work/alpha" in text
    assert "gamma, nothing reported" in text
    assert "delta, reported 5m ago, runs unreadable: bad" in text
    assert "beta, " not in text


def test_no_runs_section_with_only_the_calling_machine() -> None:
    text = _text((_machine("local", calling=True, door_version=None, behind=None),))

    assert "Runs on other machines" not in text
    assert "Behind the hub" not in text
    assert text.strip() == "Nothing needs you."


def test_behind_section_lists_a_behind_and_an_ahead_entry() -> None:
    text = _text(
        (
            _machine("old", door_version=2, behind=True),
            _machine("new", door_version=4, behind=True),
        ),
        (_session(door=2, behind=True),),
    )

    assert "Behind the hub" in text
    assert "old  client 0.2.3, door 2" in text
    assert "new  client 0.2.3, door 4, ahead of the hub" in text
    assert "claude-code  beta  /work/core  client 0.2.0, door 2" in text
    assert "uv tool install --force amoeba-ai" in text
    assert "Restart the sessions" in text
    assert "hub is the one to upgrade" in text
    assert "push unconfirmed  behind" in text


def test_an_ahead_only_section_gives_no_client_command() -> None:
    text = _text((_machine("new", door_version=4, behind=True),))

    assert "hub is the one to upgrade" in text
    assert "uv tool install" not in text


def test_a_session_line_ends_behind_when_behind() -> None:
    text = _text((), (_session(door=2, behind=True),))

    line = next(row for row in text.splitlines() if "push unconfirmed" in row)
    assert line.endswith("push unconfirmed  behind")


def test_a_question_on_another_machine_renders_with_the_suffix() -> None:
    waiting = WaitingEntry(
        run_id="run-a1",
        paused_at="t",
        question="Ship?",
        slice_label=None,
        waiting_reason=None,
        waiting_detail=None,
        since=NOW - timedelta(hours=1),
        run_state=WaitingRunState.OTHER_MACHINE,
        detail=None,
        next=None,
        request_id=None,
        machine="alpha",
        machine_last_called_at=None,
    )

    text = _text((), waiting=(waiting,))

    first = next(row for row in text.splitlines() if "run-a1" in row)
    assert first.endswith("on alpha")
    assert "the run is on another machine" in text
    assert "machine: alpha" in text
