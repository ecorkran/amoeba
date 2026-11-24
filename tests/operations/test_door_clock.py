"""A client whose clock is an hour ahead changes nothing the hub stores (262 D2).

Through the door every stored time is the hub's: a step request carries no time, and
the hub stamps rows with its own clock. The client here runs a pause, an answer and its
resume, a held question, and a wake, with its clock an hour ahead of the hub's.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path

from process_containment import contained_popen
from store.message_support import NOW

from amoeba.config.user_config import UserConfig
from amoeba.operations.handle_pause import HandlePauseOutcome
from amoeba.operations.steps.dispatch import StepEdges
from amoeba.operations.wake_run import run_wake
from amoeba.store.row_values import decode_timestamp
from amoeba.store.store import Store
from amoeba.store.vocabulary import RequestState, WakeOutcome
from operations.handle_rig import World, world
from operations.held_support import add_addressee, seed_request
from operations.test_pause_held import HELD_POLLS
from operations.wake_run_support import (
    WAKE_ID,
    probe_command,
    row_of,
    seed_claimed_wake,
)
from operations.ways import DOOR, steps_on, store_for

AHEAD = timedelta(hours=1)
STORED_TIMES = (
    "SELECT claimed_at FROM questions",
    "SELECT updated_at FROM questions",
    "SELECT recorded_at FROM answers",
    "SELECT resume_at FROM answers",
    "SELECT resume_started_at FROM answers",
)


def _times(store: Store, queries: tuple[str, ...]) -> list[datetime]:
    with store.read() as transaction:
        return [
            decode_timestamp(str(row[0]), query)
            for query in queries
            for row in transaction.execute(query)
            if row[0] is not None
        ]


def _behind(w: World) -> Callable[[], datetime]:
    """The hub's clock: the client's, an hour behind."""
    return lambda: w.deps.clock() - AHEAD


def _hub_follows(w: World, clock: Callable[[], datetime]) -> None:
    """Point the world's hub at ``clock`` (the world made it follow the client's)."""
    assert w.hub_rig is not None
    w.hub_rig.follows = clock


def test_a_pause_answered_and_resumed_stores_only_the_hubs_times(
    tmp_path: Path,
) -> None:
    with world(tmp_path, way=DOOR) as w:
        _hub_follows(w, _behind(w))
        hub_now = _behind(w)()

        result = w.handle()
        stored = _times(w.store, STORED_TIMES)

    assert result.outcome is HandlePauseOutcome.RESUMED, result
    assert stored
    assert all(time <= hub_now for time in stored)


def test_a_held_question_released_by_a_done_request_stores_only_the_hubs_times(
    tmp_path: Path,
) -> None:
    with world(tmp_path, way=DOOR, paused_polls=HELD_POLLS) as w:
        _hub_follows(w, _behind(w))
        hub_now = _behind(w)()
        add_addressee(w.store)
        seed_request(w.store, RequestState.DONE)

        result = w.handle()
        stored = _times(w.store, STORED_TIMES)

    assert result.outcome is HandlePauseOutcome.RESUMED, result
    assert all(time <= hub_now for time in stored)


def test_a_wake_run_by_a_client_ahead_stores_only_the_hubs_times(
    tmp_path: Path,
) -> None:
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    with store_for(DOOR, tmp_path) as (store, hub_rig):
        assert hub_rig is not None
        hub_rig.follows = lambda: NOW
        seed_claimed_wake(store, tmp_path, probe_command(tmp_path, code=0), checkout)
        steps = steps_on(DOOR, store, StepEdges(lambda: NOW + AHEAD, _no_config))

        outcome = run_wake(steps, WAKE_ID, popen=contained_popen)
        row = row_of(store)

    assert outcome is WakeOutcome.EXITED
    assert row.ended_at == NOW


def _no_config() -> UserConfig:
    raise AssertionError("a wake step loaded the config")
