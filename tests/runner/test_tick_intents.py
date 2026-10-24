"""The apply stage in the project tick: intents land before decide, faults isolate."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from amoeba.process import ProcessSettings
from amoeba.runner.budget import TickResult
from amoeba.runner.faults import RUNNER_ACTOR
from amoeba.runner.intent import apply as apply_module
from amoeba.runner.lifecycle.human_steps import HumanStepPlanner
from amoeba.runner.lifecycle.steps import LifecycleStep
from amoeba.runner.tenant import RunnerTenant
from amoeba.store import (
    AcknowledgmentOutcome,
    Channel,
    NodeKind,
    NodeStatus,
    Store,
    StoreBusyError,
)
from runner.observe_support import CfReply
from runner.plan_tick_support import INITIATIVES_KEY, initiatives_json, slices_key
from runner.tick_support import PROJECT, Rig, link

from .intent.intent_support import submit

SETTINGS = ProcessSettings(tick_deadline_seconds=5.0, run_poll_interval_seconds=15.0)
LINK = "cf-1"


@pytest.fixture
def rig(tmp_path: Path, store: Store) -> Rig:
    built = Rig(tmp_path, store)
    built.planners = ()
    return built


class _Host:
    stop_requested = False
    project_ids = (PROJECT,)

    def __init__(self, store: Store) -> None:
        self._store = store

    def store_for(self, project_id: str) -> Store:
        return self._store


def _tenant(rig: Rig) -> RunnerTenant:
    return RunnerTenant(
        settings=SETTINGS,
        supervisor_dir=rig.supervisor_dir,
        planners=rig.planners,
        popen=rig.popen,
        cf_run=rig.cf,
        poll=rig.poll,
        now=rig.clock.wall,
        monotonic=rig.clock.monotonic,
    )


def _intent(store: Store, message_id: str) -> Any:
    [found] = [
        m for m in store.messages(PROJECT, channel=Channel.INTENT) if m.id == message_id
    ]
    return found


def test_an_intent_is_acknowledged_and_its_row_written_in_the_tick(
    rig: Rig, store: Store
) -> None:
    message_id = submit(store, {"intent": "pause"}, project_id=PROJECT)

    result, tick = rig.tick()

    assert result is TickResult.COMPLETE and tick.wrote
    message = _intent(store, message_id)
    assert message.acknowledgment_outcome is AcknowledgmentOutcome.APPLIED
    assert message.acknowledged_by == RUNNER_ACTOR
    row = store.desired_state(PROJECT)
    assert row is not None and row.hold is True and row.message_id == message_id


def test_a_tick_that_only_applied_an_intent_reports_a_write(
    rig: Rig, store: Store
) -> None:
    submit(store, {"intent": "pause"}, project_id=PROJECT)
    assert _tenant(rig).tick(_Host(store)) is True
    assert _tenant(rig).tick(_Host(store)) is False


def test_a_driven_initiative_without_arch_file_is_blocked_in_the_same_tick(
    rig: Rig, store: Store
) -> None:
    rig.planners = (HumanStepPlanner(),)
    link(store, "s-1", LINK, PROJECT)
    rig.cf.replies[INITIATIVES_KEY] = CfReply(initiatives_json(140, arch_file=None))
    rig.cf.replies[slices_key(140)] = CfReply("", 1, '{"error":true,"code":"UNKNOWN"}')
    submit(store, {"intent": "drive"}, project_id=PROJECT)

    rig.tick()

    [architecture] = [
        n
        for n in store.nodes_for_project(PROJECT)
        if n.kind is NodeKind.PHASE_OR_ARTIFACT
        and n.cf.phase == LifecycleStep.ARCHITECTURE.value
    ]
    stored = store.get_node(architecture.id)
    assert stored is not None and stored.status is NodeStatus.BLOCKED_ON_HUMAN


def _break_interpret(monkeypatch: pytest.MonkeyPatch, fail_for: str | None) -> None:
    real = apply_module.interpret

    def interpret(message: Any, tree: Any, row: Any) -> Any:
        if fail_for is None or message.id == fail_for:
            raise RuntimeError("interpret exploded")
        return real(message, tree, row)

    monkeypatch.setattr(apply_module, "interpret", interpret)


def test_an_unexpected_apply_exception_is_one_project_fault(
    rig: Rig, store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    good = submit(store, {"intent": "pause"}, project_id=PROJECT)
    bad = submit(store, {"intent": "drive"}, project_id=PROJECT)
    _break_interpret(monkeypatch, fail_for=bad)
    tenant = _tenant(rig)

    tenant.tick(_Host(store))

    assert [m.fault_kind for m in store.open_project_escalations(PROJECT)] == [
        "unexpected_fault"
    ]
    assert _intent(store, good).acknowledgment_outcome is AcknowledgmentOutcome.APPLIED
    assert [m.id for m in store.pending_intents(PROJECT)] == [bad]
    [escalation] = store.open_project_escalations(PROJECT)
    assert escalation.node_id is None, "project-scoped: the context was cleared"


def test_a_repeating_apply_bug_adds_no_second_escalation(
    rig: Rig, store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    submit(store, {"intent": "drive"}, project_id=PROJECT)
    _break_interpret(monkeypatch, fail_for=None)
    tenant = _tenant(rig)

    for _ in range(3):
        tenant.tick(_Host(store))

    assert len(store.messages(PROJECT, channel=Channel.ESCALATION)) == 1


def test_a_store_failure_in_apply_exits_the_tick(
    rig: Rig, store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    submit(store, {"intent": "drive"}, project_id=PROJECT)

    def locked(*_: object, **__: object) -> None:
        raise StoreBusyError("locked")

    monkeypatch.setattr(store, "acknowledge_message", locked)

    with pytest.raises(StoreBusyError):
        _tenant(rig).tick(_Host(store))
    assert store.open_project_escalations(PROJECT) == []
