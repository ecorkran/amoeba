"""Waking against real ``cf`` and the real ``amoeba`` script (slice 244, 9.2).

The Verification Walkthrough's steps 3 to 7, then the live-session, note, message-text
and SIGKILL cases. A sender and a woken member are committed git repos in one program
and one throwaway ``AMOEBA_HOME``; the woken member's wake command is a fixture script
that runs ``amoeba inbox`` and ``amoeba reply``, so nothing is spent. The throwaway
config gives ``wake_timeout_seconds`` 5 and ``max_wakes_per_day`` 2; the contract's
example keeps its suggested values.
"""

from __future__ import annotations

import json
import os
import shlex
import signal
import sqlite3
import sys
from contextlib import closing
from datetime import UTC, datetime, timedelta
from typing import Any

from store_open import open_local_store

from amoeba.operations.wake_environment import WAKE_ENV_NAMES
from amoeba.store.message_sweep import sweep
from amoeba.store.row_values import encode_timestamp
from live.waking.world import (
    MAX_WAKES_PER_DAY,
    RECIPIENT_NAME,
    RECORDER,
    WAKE_TIMEOUT_SECONDS,
    WakingWorld,
    agent_command,
    amoeba,
    group_exists,
    member_wake,
    process_exists,
    request_states,
    send,
    set_wake_command,
    wait_for_end,
    wait_for_row,
    wait_until,
    wake_rows,
)

#: Each marker is long and unlike anything else a command or its environment holds.
SUBJECT_MARKER = "SUBJECT-MARKER-6f3a9c"
BODY_MARKER = "BODY-MARKER-2b81d7"
RETENTION_DAYS = 30
#: A name macOS adds to every process it starts, whatever the parent passed.
OS_ADDED_NAMES = {"__CF_USER_TEXT_ENCODING"}


def _member_id(world: WakingWorld) -> str:
    listed = amoeba(world.sender, "list", "members")
    (row,) = [m for m in listed["members"] if m["name"] == RECIPIENT_NAME]
    project_id: str = row["project_id"]
    return project_id


def test_the_store_amoeba_uses_is_the_throwaway_one(waking: WakingWorld) -> None:
    assert waking.sender.store.is_file()
    assert waking.sender.store.is_relative_to(waking.sender.amoeba_home)
    assert waking.sender.amoeba_home == waking.recipient.amoeba_home


def test_a_request_wakes_the_fixture_once_and_a_second_is_in_its_inbox(
    waking: WakingWorld,
) -> None:
    gate = waking.sender.repo.parent / "gate"
    set_wake_command(waking, agent_command(waking, "--gate-file", str(gate)))

    first = send(waking, "w-1")
    assert first["outcome"] == "sent"
    wait_for_row(
        waking, lambda row: row.command_pid is not None, "the wake to start", 30
    )
    send(waking, "w-2")
    # Opened at once: the wake's own timeout (5 s) is running.
    gate.write_text("open", encoding="utf-8")
    assert len(wake_rows(waking)) == 1

    ended = wait_for_end(waking)

    assert (ended.outcome, ended.exit_code) == ("exited", 0)
    assert len(wake_rows(waking)) == 1
    assert request_states(waking) == {"w-1": "done", "w-2": "done"}
    after = member_wake(waking)
    assert after is not None
    assert (after["running"], after["last_problem"]) == (None, None)


def test_list_shows_a_live_wake_as_running(waking: WakingWorld) -> None:
    gate = waking.sender.repo.parent / "never-opened"
    command = agent_command(waking, "--gate-file", str(gate))
    set_wake_command(waking, command)
    send(waking, "w-1")
    started = wait_for_row(
        waking, lambda row: row.command_pid is not None, "the wake to start", 30
    )
    assert started.command_pid is not None
    waking.command_pids.append(started.command_pid)

    wake = member_wake(waking)

    assert wake is not None
    assert wake["command"] == command
    assert wake["running"]["command_pid"] == started.command_pid
    assert wake["running"]["log_stem"] == started.log_stem


def test_the_limit_stops_the_next_wake_and_the_request_stays_open(
    waking: WakingWorld,
) -> None:
    set_wake_command(waking, agent_command(waking))
    for index in range(MAX_WAKES_PER_DAY):
        send(waking, f"ok-{index}")
        wait_for_end(waking, index)

    send(waking, "over-the-limit")

    assert len(wake_rows(waking)) == MAX_WAKES_PER_DAY
    assert request_states(waking)["over-the-limit"] == "open"
    wake = member_wake(waking)
    assert wake is not None
    assert wake["stopped"] == {"used": MAX_WAKES_PER_DAY, "limit": MAX_WAKES_PER_DAY}


def test_a_missing_executable_ends_start_failed_and_the_request_stays_open(
    waking: WakingWorld,
) -> None:
    set_wake_command(waking, "/nonexistent/wake-agent --flag")

    send(waking, "w-1")

    ended = wait_for_end(waking)
    assert ended.outcome == "start_failed"
    assert ended.detail == "FileNotFoundError: No such file or directory"
    assert request_states(waking) == {"w-1": "open"}
    wake = member_wake(waking)
    assert wake is not None
    assert wake["last_problem"]["outcome"] == "start_failed"
    assert wake["last_problem"]["detail"] == ended.detail


def test_a_command_that_sleeps_past_the_timeout_is_stopped_with_its_group(
    waking: WakingWorld,
) -> None:
    set_wake_command(waking, agent_command(waking, "--sleep-seconds", "50"))

    send(waking, "w-1")

    ended = wait_for_end(waking)
    assert ended.outcome == "timed_out"
    assert ended.command_pid is not None
    waking.command_pids.append(ended.command_pid)
    wait_until(
        lambda: not group_exists(ended.command_pid or 0),
        "the stopped command's process group to be gone",
        10,
    )
    wake = member_wake(waking)
    assert wake is not None
    assert wake["last_problem"]["outcome"] == "timed_out"
    assert request_states(waking) == {"w-1": "open"}


def test_clearing_the_command_leaves_a_later_send_starting_nothing(
    waking: WakingWorld,
) -> None:
    set_wake_command(waking, agent_command(waking))
    send(waking, "w-1")
    wait_for_end(waking)

    amoeba(waking.recipient, "add", "--no-wake-command")
    send(waking, "w-2")

    assert len(wake_rows(waking)) == 1
    listed = amoeba(waking.sender, "list", "members")
    (row,) = [m for m in listed["members"] if m["name"] == RECIPIENT_NAME]
    assert row["wake_command"] is None
    assert member_wake(waking) is None
    assert request_states(waking)["w-2"] == "open"


def _write_session(world: WakingWorld, *, confirmed: bool) -> None:
    """A fresh ``sessions`` row for the woken member, as its ``amoeba-mcp`` would."""
    now = encode_timestamp(datetime.now(UTC))
    with closing(sqlite3.connect(world.sender.store)) as connection, connection:
        connection.execute("DELETE FROM sessions")
        connection.execute(
            "INSERT INTO sessions (session_id, member_id, client, directory, "
            "started_at, heartbeat_at, push_confirmed_at, owner_id, machine_id) "
            "VALUES ('fixture-session', ?, 'fixture', '/work', ?, ?, ?, "
            "(SELECT owner_id FROM owners), "
            "(SELECT machine_id FROM machines WHERE name = 'local'))",
            (_member_id(world), now, now, now if confirmed else None),
        )


def test_a_confirmed_live_session_blocks_the_wake_and_an_unconfirmed_one_does_not(
    waking: WakingWorld,
) -> None:
    set_wake_command(waking, agent_command(waking))

    _write_session(waking, confirmed=True)
    send(waking, "blocked")
    assert wake_rows(waking) == []

    _write_session(waking, confirmed=False)
    send(waking, "woken")

    wait_for_end(waking)
    assert len(wake_rows(waking)) == 1


def test_a_note_to_a_member_with_a_command_starts_nothing(
    waking: WakingWorld,
) -> None:
    set_wake_command(waking, agent_command(waking))

    sent = send(waking, "fyi", kind_note=True)

    assert sent["note"] is not None
    assert wake_rows(waking) == []


def test_the_command_receives_no_message_text(waking: WakingWorld) -> None:
    output = waking.sender.repo.parent / "recorded.json"
    set_wake_command(waking, shlex.join([sys.executable, str(RECORDER), str(output)]))

    send(
        waking,
        "w-1",
        "--subject",
        SUBJECT_MARKER,
        "--body",
        BODY_MARKER,
    )

    ended = wait_for_end(waking)
    assert (ended.outcome, ended.exit_code) == ("exited", 0)
    recorded: dict[str, Any] = json.loads(output.read_text(encoding="utf-8"))
    everything = json.dumps(recorded)
    assert SUBJECT_MARKER not in everything
    assert BODY_MARKER not in everything
    assert recorded["stdin"] == ""
    # Only names the wrapper itself had can be judged (macOS adds some of its own).
    inherited = set(recorded["environment"]) & set(os.environ) - OS_ADDED_NAMES
    assert inherited <= set(WAKE_ENV_NAMES)


def test_a_killed_wrapper_leaves_an_overdue_row_and_a_command_amoeba_never_stops(
    waking: WakingWorld,
) -> None:
    pid_file = waking.sender.repo.parent / "wrapper.pid"
    gate = waking.sender.repo.parent / "never-opened"
    set_wake_command(
        waking,
        agent_command(
            waking, "--parent-pid-file", str(pid_file), "--gate-file", str(gate)
        ),
    )
    send(waking, "w-1")
    running = wait_for_row(
        waking, lambda row: row.command_pid is not None, "the command to start", 30
    )
    assert running.command_pid is not None
    waking.command_pids.append(running.command_pid)
    wait_until(pid_file.exists, "the fixture agent to name its parent", 30)
    os.kill(int(pid_file.read_text(encoding="utf-8")), signal.SIGKILL)

    # Live until its deadline, then overdue with the pid and log path.
    wait_until(
        lambda: (member_wake(waking) or {}).get("running", {}).get("overdue") is True,
        "the killed wrapper's row to read as overdue",
        WAKE_TIMEOUT_SECONDS + 30,
    )
    wake = member_wake(waking)
    assert wake is not None
    assert wake["running"]["command_pid"] == running.command_pid
    assert wake["running"]["log_stem"] == running.log_stem
    assert wake_rows(waking)[0].ended_at is None
    assert process_exists(running.command_pid), "Amoeba must not signal the old command"

    # The next send starts a new wake beside it.
    send(waking, "w-2")
    wait_for_row(
        waking,
        lambda row: row.wake_id != running.wake_id and row.command_pid is not None,
        "the second wake to start",
        30,
    )
    assert len(wake_rows(waking)) == 2
    assert process_exists(running.command_pid)

    # The test stops both commands itself, then the sweep deletes the rows by age.
    for row in wake_rows(waking):
        if row.command_pid is not None:
            waking.command_pids.append(row.command_pid)
            os.killpg(row.command_pid, signal.SIGKILL)
    wait_until(
        lambda: all(row.ended_at is not None for row in wake_rows(waking)[1:]),
        "the second wrapper to record its end",
        WAKE_TIMEOUT_SECONDS + 30,
    )
    later = datetime.now(UTC) + timedelta(days=RETENTION_DAYS + 1)
    with open_local_store(waking.sender.store) as store, store.write() as transaction:
        sweep(transaction, later, RETENTION_DAYS)
    assert wake_rows(waking) == []
