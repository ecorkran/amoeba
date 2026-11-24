"""The waking tier with the sender and the woken member on two machines (slice 262, D8,
D10, D16, task 8.5).

A real hub process and two joined client homes (``hub_fixture.two_machine_hub``),
each with the real ``cf`` and ``git`` and its own Context Forge data directory
(``live.machines.Machine``). The sender's checkout is on ``alpha``; the woken member's
checkout, the only one with a wake command, is on ``beta``. The wake command is the
single-machine tier's fixture agent, so nothing is spent. The hub's store is only
read; whatever a case leaves running is stopped afterwards.
"""

from __future__ import annotations

import os
import signal
import sqlite3
from collections.abc import Generator
from contextlib import closing, contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from hub_fixture import FIRST, SECOND, FixtureHub

from live.machines import Machine
from live.waking.world import RECIPIENT_NAME, WakeRow, read_wake_rows

SENDER_NAME: Final = "send-s"
PROGRAM: Final = "live-waking"
#: The machine each wake was claimed by, oldest first.
WAKE_MACHINES_SQL: Final = (
    "SELECT m.name FROM wakes AS w LEFT JOIN machines AS m "
    "ON m.machine_id = w.machine_id ORDER BY w.started_at"
)


@dataclass(frozen=True)
class SplitWaking:
    """``sender`` is a checkout on ``alpha``; ``recipient`` one on ``beta``."""

    hub: FixtureHub
    alpha: Machine
    beta: Machine
    sender: Path
    recipient: Path

    @property
    def store(self) -> Path:
        return self.hub.layout.store_path


def build_split_waking(hub: FixtureHub) -> SplitWaking:
    alpha = Machine(hub, hub.clients[FIRST])
    beta = Machine(hub, hub.clients[SECOND])
    split = SplitWaking(
        hub=hub,
        alpha=alpha,
        beta=beta,
        sender=alpha.repo(SENDER_NAME),
        recipient=beta.repo(RECIPIENT_NAME),
    )
    for machine, repo in ((alpha, split.sender), (beta, split.recipient)):
        added = machine.run(repo, "add", "--program", PROGRAM)
        assert added["outcome"] == "applied", added
    return split


def send_from_alpha(split: SplitWaking, request_id: str) -> dict[str, Any]:
    return split.alpha.run(
        split.sender,
        "send",
        "--id",
        request_id,
        "--to",
        RECIPIENT_NAME,
        "--subject",
        f"subject of {request_id}",
        "--body",
        f"body of {request_id}",
    )


def sender_request_states(split: SplitWaking) -> dict[str, str]:
    """The sender's requests by id and state, from its ``inbox`` on ``alpha``."""
    inbox = split.alpha.run(split.sender, "inbox")
    return {request["id"]: request["state"] for request in inbox["requests"]}


def wake_rows(split: SplitWaking) -> list[WakeRow]:
    return read_wake_rows(split.store)


def wake_machines(split: SplitWaking) -> list[str | None]:
    uri = f"file:{split.store}?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as connection:
        rows = connection.execute(WAKE_MACHINES_SQL).fetchall()
    return [None if name is None else str(name) for (name,) in rows]


@contextmanager
def reaping(split: SplitWaking) -> Generator[SplitWaking]:
    """Whatever a case leaves running is stopped, its whole group, when it ends."""
    try:
        yield split
    finally:
        for row in wake_rows(split):
            if row.command_pid is None:
                continue
            try:
                os.killpg(row.command_pid, signal.SIGKILL)
            except ProcessLookupError:
                # Expected: the command already ended, which is what the case wants.
                continue
