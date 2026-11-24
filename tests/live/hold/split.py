"""The hold tier with its two repos on two machines (slice 262, D10, D16, task 8.5).

A real hub process and two joined client homes (``hub_fixture.two_machine_hub``): the
asking repo's checkout is on ``alpha``, the repo the request goes to is on ``beta``.
``alpha`` runs the real ``sq`` with the configured models, so it has the real ``HOME``
and the provider credentials (``pipeline_environment``) and the inert hook stub first
on ``PATH``; ``beta`` has only the real ``cf`` and ``git``. The hub's ``config.yaml``
carries the live settings, because the hub hands the answering settings out. Each
machine is a ``PauseWorld`` whose home is its client home, so the single-machine
harness's send, pause, hold and reply calls run unchanged on the machine that owns
them. The store is the hub's; it is only read, and the poll reads it and ``sq`` alone,
so no ``amoeba`` call of the poll can start work on ``alpha``.
"""

from __future__ import annotations

import os
import sqlite3
import sys
import time
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from hub_fixture import FIRST, SECOND, FixtureHub
from live_environment import pipeline_environment
from live_settings import LiveSettings

from amoeba.upstream.squadron.run_outcome import RunPoll, poll_run
from live.hold.harness import (
    AUTO_RESUME_WAIT_SECONDS,
    POLL_CALL_TIMEOUT_SECONDS,
    POLL_INTERVAL_SECONDS,
    QUESTION_ENDED_STATES,
    HoldWorld,
    amoeba_document,
)
from live.machines import Machine
from live.messaging.repos import FORGE_NAME
from live.pause.harness import (
    CF_PROJECT_NAME,
    PROGRAM_ID,
    RULE_FILE,
    RULE_TEXT,
    PauseWorld,
    inert_amoeba_dir,
    write_config,
)

#: The question row of a run, with the name of the machine it belongs to.
QUESTION_SQL: Final = (
    "SELECT q.state, q.waiting_reason, q.request_id, q.start_count, m.name "
    "FROM questions AS q LEFT JOIN machines AS m ON m.machine_id = q.machine_id "
    "WHERE q.run_id = ?"
)
RESUME_SQL: Final = "SELECT resume_outcome FROM answers WHERE run_id = ? ORDER BY seq"


@dataclass(frozen=True)
class SplitHold:
    """``hold.asker`` is ``alpha``'s checkout; ``hold.addressee`` is ``beta``'s."""

    hub: FixtureHub
    hold: HoldWorld


@dataclass(frozen=True)
class SplitObserved:
    """One read of the hub's store and the run."""

    state: str | None
    waiting_reason: str | None
    request_id: str | None
    start_count: int | None
    machine: str | None
    resume_outcome: str | None
    poll: RunPoll


def _alpha_extra(home: Path) -> dict[str, str]:
    """What ``alpha`` needs to run ``sq`` with models: the named pipeline variables,
    and a ``PATH`` with the inert hook stub, then this build's ``amoeba``."""
    path = os.pathsep.join(
        [
            str(inert_amoeba_dir(home)),
            str(Path(sys.executable).parent),
            os.environ["PATH"],
        ]
    )
    return {**pipeline_environment(os.environ), "PATH": path}


def _member(
    machine: Machine, name: str, settings: LiveSettings, files: dict[str, str]
) -> PauseWorld:
    """A repo on ``machine``, a member of the program, as a ``PauseWorld``."""
    repo = machine.repo(name, files)
    world = PauseWorld(repo, machine.environ, machine.client.home, settings)
    amoeba_document(world, "add", "--program", PROGRAM_ID)
    return world


def build_split_hold(hub: FixtureHub, settings: LiveSettings) -> SplitHold:
    write_config(PauseWorld(hub.home, {}, hub.home, settings))
    alpha_client = hub.clients[FIRST]
    alpha = Machine(hub, alpha_client, _alpha_extra(alpha_client.home))
    beta = Machine(hub, hub.clients[SECOND])
    asker = _member(alpha, CF_PROJECT_NAME, settings, {RULE_FILE: RULE_TEXT})
    addressee = _member(beta, FORGE_NAME, settings, {})
    return SplitHold(hub=hub, hold=HoldWorld(asker=asker, addressee=addressee))


def _rows(split: SplitHold, statement: str, run_id: str) -> list[tuple[object, ...]]:
    uri = f"file:{split.hub.layout.store_path}?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as connection:
        return [tuple(row) for row in connection.execute(statement, (run_id,))]


def _text(value: object) -> str | None:
    return None if value is None else str(value)


def observe(split: SplitHold, run_id: str) -> SplitObserved:
    rows = _rows(split, QUESTION_SQL, run_id)
    state = reason = request = count = machine = None
    if rows:
        ((state, reason, request, count, machine),) = rows
    outcomes = _rows(split, RESUME_SQL, run_id)
    return SplitObserved(
        state=_text(state),
        waiting_reason=_text(reason),
        request_id=_text(request),
        start_count=None if count is None else int(str(count)),
        machine=_text(machine),
        resume_outcome=_text(outcomes[-1][0]) if outcomes else None,
        poll=poll_run(run_id, timeout_seconds=POLL_CALL_TIMEOUT_SECONDS),
    )


def held_question_ended(observed: SplitObserved) -> bool:
    """The question left the hold and, if answered, the resume has an outcome."""
    if observed.state not in QUESTION_ENDED_STATES:
        return False
    return observed.state != "answered" or observed.resume_outcome is not None


def poll_until_ended(split: SplitHold, run_id: str) -> SplitObserved:
    """Read every ``POLL_INTERVAL_SECONDS`` until the held question ended; at
    ``AUTO_RESUME_WAIT_SECONDS`` fail with the last read."""
    deadline = time.monotonic() + AUTO_RESUME_WAIT_SECONDS
    observed = observe(split, run_id)
    while not held_question_ended(observed):
        if time.monotonic() >= deadline:
            raise AssertionError(
                f"the held question of run {run_id} had not ended after "
                f"{AUTO_RESUME_WAIT_SECONDS}s; last read: {observed}"
            )
        time.sleep(POLL_INTERVAL_SECONDS)
        observed = observe(split, run_id)
    return observed
