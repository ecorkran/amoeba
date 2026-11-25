"""Shared set-up for the cross-machine session tests (slice 263, 8.2 to 8.5): a hub
on short timings, a sender on ``alpha`` and a receiver on ``beta`` in one program."""

from __future__ import annotations

import json
import sqlite3
import stat
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from hub_fixture import FIRST, SECOND, ClientHome, FixtureHub
from hub_mcp import set_hub_timings

#: Short timings, valid under the three checks (poll <= heartbeat, stale >= 2 beats and
#: >= a beat plus two polls).
POLL_SECONDS: Final = 0.3
HEARTBEAT_SECONDS: Final = 0.6
STALE_SECONDS: Final = 3.0
PROGRAM: Final = "shared"
SENDER: Final = "sender"
RECEIVER: Final = "receiver"
#: Each repo has its own origin, so each is its own member.
SENDER_ORIGIN: Final = "git@github.com:org/sender.git"
RECEIVER_ORIGIN: Final = "https://github.com/org/receiver.git"


@dataclass
class Machines:
    hub: FixtureHub
    alpha: ClientHome
    beta: ClientHome
    sender_repo: Path
    receiver_repo: Path
    woke: Path

    def sessions_by_member(self, viewer: ClientHome) -> dict[str, list[dict[str, Any]]]:
        """The live sessions ``list -j`` from ``viewer`` shows, under each member's name
        (a member with none is left out)."""
        done = viewer.run("list", "-j")
        assert done.code == 0, done.err
        listed = json.loads(done.out)
        return {
            member["member"]["name"]: member["sessions"]
            for program in listed["programs"]
            for member in program["members"]
            if member["sessions"]
        }

    def sessions(self, viewer: ClientHome) -> list[dict[str, Any]]:
        """The live sessions ``list -j`` from ``viewer`` shows, over every member."""
        return [
            session
            for sessions in self.sessions_by_member(viewer).values()
            for session in sessions
        ]

    def session_rows(self) -> list[str]:
        """The session ids in the hub's table, live or stale, read on a plain
        connection (which never migrates or prunes)."""
        with closing(sqlite3.connect(self.hub.layout.store_path)) as connection:
            return [
                str(row[0])
                for row in connection.execute("SELECT session_id FROM sessions")
            ]

    def send(self, request_id: str) -> dict[str, Any]:
        """A request from the sender (alpha) to the receiver (beta), as the CLI."""
        done = self.alpha.run_in(
            self.sender_repo,
            "send",
            "--id",
            request_id,
            "--to",
            RECEIVER,
            "--subject",
            "s",
            "--body",
            "b",
            "-j",
        )
        assert done.code == 0, done.err + done.out
        result: dict[str, Any] = json.loads(done.out)
        return result


def _wake_script(directory: Path, marker: Path) -> Path:
    script = directory / "wake.sh"
    script.write_text(f"#!/bin/sh\ntouch {marker}\n", encoding="utf-8")
    script.chmod(script.stat().st_mode | stat.S_IXUSR)
    return script


def build_machines(hub: FixtureHub, *, wake: bool = False) -> Machines:
    """The timings set, the sender added on alpha and the receiver on beta; with
    ``wake`` the receiver's checkout has a command that touches ``woke``."""
    set_hub_timings(
        hub,
        notify_poll_seconds=POLL_SECONDS,
        session_heartbeat_seconds=HEARTBEAT_SECONDS,
        session_stale_seconds=STALE_SECONDS,
    )
    alpha, beta = hub.clients[FIRST], hub.clients[SECOND]
    sender_repo = alpha.clone(SENDER, SENDER_ORIGIN, "cf-sender", SENDER)
    receiver_repo = beta.clone(RECEIVER, RECEIVER_ORIGIN, "cf-receiver", RECEIVER)
    woke = hub.root / "woke"
    for client, repo, extra in (
        (alpha, sender_repo, []),
        (
            beta,
            receiver_repo,
            ["--wake-command", str(_wake_script(hub.root, woke))] if wake else [],
        ),
    ):
        done = client.run_in(repo, "add", "--program", PROGRAM, *extra, "-j")
        assert done.code == 0, done.err + done.out
    return Machines(hub, alpha, beta, sender_repo, receiver_repo, woke)
