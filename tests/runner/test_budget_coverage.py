"""No subprocess call starts once the tick budget is spent (D10).

Every subprocess call the tick can make (the poll, a ``cf`` probe, ``Popen``) is
wrapped so that it fails the test if it begins after the deadline. A new call
site that skips ``TickBudget.allows_call`` fails here.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from amoeba.process import RunOutcome
from amoeba.runner.budget import TickResult
from amoeba.runner.launch import PARAM_PARAMS, PARAM_PIPELINE
from amoeba.store import PARAM_RUN_ID, CommandKind, NodeKind, Store
from runner.observe_support import Child, document
from runner.tick_support import PROJECT, Rig, link

DEADLINE = 5.0
CALL_COST = 2.0


@pytest.fixture
def busy_rig(tmp_path: Path, store: Store) -> Rig:
    """Three confirmed runs due a poll, an unprobed link and two runnable nodes."""
    rig = Rig(tmp_path, store)
    for index in range(3):
        node = store.create_node(
            project_id=PROJECT, kind=NodeKind.SLICE, title=f"running-{index}"
        )
        entry = store.journal_issue(
            node.id,
            kind=CommandKind.SQ_RUN,
            parameters={
                PARAM_PIPELINE: "p",
                PARAM_PARAMS: {},
                PARAM_RUN_ID: f"run-{index}",
            },
        )
        rig.tracker.track(entry.id, Child(None))
        rig.tracker.confirm(entry.id)
    link(store, "s-1", "cf-1", PROJECT)
    for index in range(2):
        store.create_node(
            project_id=PROJECT, kind=NodeKind.SLICE, title=f"free-{index}"
        )
    return rig


def _guard(rig: Rig, started: list[str]) -> None:
    """Make each call record itself, fail if the deadline passed, and cost time."""

    def call(kind: str) -> None:
        started.append(kind)
        assert rig.clock.seconds < DEADLINE, f"a {kind} call started after the deadline"
        rig.clock.seconds += CALL_COST

    rig.poll.on_call = lambda: call("poll")
    rig.cf.on_call = lambda: call("cf")
    rig.popen.on_call = lambda: call("popen")


def test_no_call_starts_after_the_deadline_while_a_tick_spends_its_budget(
    busy_rig: Rig,
) -> None:
    rig = busy_rig
    rig.deadline = DEADLINE
    rig.poll.answers.extend(
        document(f"run-{i}", RunOutcome.TIMED_OUT) for i in range(3)
    )
    started: list[str] = []
    _guard(rig, started)

    result, _ = rig.tick()

    assert result is TickResult.CUT_OFF
    assert 0 < len(started) <= 3, "the budget let a few calls through, then stopped"


def test_no_call_starts_when_the_budget_is_spent_before_the_tick(
    busy_rig: Rig,
) -> None:
    rig = busy_rig
    rig.deadline = 0.0
    started: list[str] = []
    _guard(rig, started)

    result, tick = rig.tick()

    assert result is TickResult.CUT_OFF and not tick.wrote
    assert started == []
    assert rig.poll.asked == [] and rig.cf.calls == [] and rig.popen.calls == 0
