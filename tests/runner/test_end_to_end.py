"""The Runner against the stub ``sq``, in process: launch, fault and shape paths."""

from __future__ import annotations

import os
import time
from collections.abc import Callable, Iterator, Sequence
from pathlib import Path

import pytest
from sq_stub import (
    RUN_LATE_SECONDS_ENV,
    RUN_MODE_ENV,
    RUN_SECONDS_ENV,
    RunMode,
    write_sq_stub,
)

from amoeba.process import ProcessSettings, UpstreamShapeError
from amoeba.runner import RunnerTenant, runner_tenant
from amoeba.runner.decide import Action, LaunchRun, ProjectView
from amoeba.runner.ingest.record import (
    RESULT_OUTCOME,
    RESULT_RUN_ID,
    RESULT_STATUS,
    RESULT_VERDICT_IDS,
)
from amoeba.runner.launch import log_paths
from amoeba.store import (
    PARAM_RUN_ID,
    JournalEntry,
    JournalOutcome,
    Node,
    NodeStatus,
    Store,
)
from runner.tick_support import drive_project, ready_step, runnable_unbusy

PROJECT = "demo"
GRACE_SECONDS = 0.5
WAIT_SECONDS = 20.0

SETTINGS = ProcessSettings(
    launch_grace_seconds=GRACE_SECONDS,
    run_poll_interval_seconds=0.1,
    tick_deadline_seconds=5.0,
    tick_call_timeout_seconds=4.0,
    shutdown_grace_seconds=10.0,
)

pytestmark = pytest.mark.usefixtures("passing_checks")


class Host:
    stop_requested = False

    def __init__(self, store: Store) -> None:
        self._store = store
        self.project_ids = (PROJECT,)

    def store_for(self, project_id: str) -> Store:
        assert project_id == PROJECT
        return self._store


class OncePerNode:
    """The test planner: launch the no-op pipeline once for each node it sees."""

    def __init__(self, checkout: Path) -> None:
        self._checkout = checkout
        self._launched: set[str] = set()

    def plan(self, view: ProjectView) -> Sequence[Action]:
        fresh = [n for n in runnable_unbusy(view) if n.id not in self._launched]
        self._launched.update(n.id for n in fresh)
        return [LaunchRun(n.id, "P4", {}, self._checkout) for n in fresh]


class Scenario:
    def __init__(self, tmp_path: Path, store: Store, monkeypatch: pytest.MonkeyPatch):
        home = tmp_path / "home"
        home.mkdir()
        self.supervisor_dir = tmp_path / "supervisor"
        checkout = tmp_path / "checkout"
        checkout.mkdir()
        monkeypatch.setenv("HOME", str(home))
        bin_dir = write_sq_stub(tmp_path / "bin")
        monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
        monkeypatch.setenv(RUN_SECONDS_ENV, "0.2")
        self.monkeypatch = monkeypatch
        self.store = store
        self.host = Host(store)
        self.node: Node = ready_step(store)
        drive_project(store)
        self.planner = OncePerNode(checkout)
        self._tenant: RunnerTenant | None = None

    @property
    def tenant(self) -> RunnerTenant:
        if self._tenant is None:
            self._tenant = runner_tenant(
                SETTINGS, self.supervisor_dir, planners=(self.planner,)
            )
        return self._tenant

    def tick_until(self, description: str, done: Callable[[], bool]) -> None:
        """Tick the Runner until ``done``; fail rather than hang."""
        deadline = time.monotonic() + WAIT_SECONDS
        while not done():
            if time.monotonic() >= deadline:
                raise AssertionError(f"timed out waiting for {description}")
            self.tenant.tick(self.host)
            time.sleep(0.05)

    def entry(self) -> JournalEntry:
        [entry] = self.store.journal_entries(PROJECT)
        return entry

    def resolved(self) -> bool:
        entries = self.store.journal_entries(PROJECT)
        return len(entries) == 1 and entries[0].is_resolved

    def escalations(self) -> list[str]:
        return [
            m.fault_kind or "" for m in self.store.open_project_escalations(PROJECT)
        ]


@pytest.fixture
def scenario(
    tmp_path: Path, store: Store, monkeypatch: pytest.MonkeyPatch
) -> Iterator[Scenario]:
    yield Scenario(tmp_path, store, monkeypatch)


def test_the_normal_path_records_run_id_outcome_and_status(scenario: Scenario) -> None:
    scenario.tick_until("the entry to be resolved", scenario.resolved)

    entry = scenario.entry()
    run_id = str(entry.parameters[PARAM_RUN_ID])
    assert entry.outcome is JournalOutcome.COMPLETED
    assert entry.result is not None
    assert entry.result[RESULT_RUN_ID] == run_id
    assert entry.result[RESULT_OUTCOME] == "completed"
    assert entry.result[RESULT_STATUS] == "completed"
    assert entry.result[RESULT_VERDICT_IDS] == []
    node = scenario.store.get_node(scenario.node.id)
    assert node is not None and node.status is NodeStatus.DONE
    stderr = log_paths(scenario.supervisor_dir, entry.id).stderr.read_text()
    assert f"run_id={run_id}\n" in stderr, "confirmed by its own line"
    assert scenario.escalations() == []


def test_exit_before_the_line_fails_the_launch_and_blocks_the_node(
    scenario: Scenario,
) -> None:
    scenario.monkeypatch.setenv(RUN_MODE_ENV, RunMode.EXIT_BEFORE_LINE.value)

    scenario.tick_until("the entry to be resolved", scenario.resolved)

    entry = scenario.entry()
    assert entry.outcome is JournalOutcome.FAILED
    assert entry.result is not None
    assert entry.result["launch_failure"] == "exited_before_line"
    blocked = scenario.store.blocked_state_for(scenario.node.id)
    assert blocked is not None
    assert "exited_before_line" in blocked.context and "exit code 1" in blocked.context


def test_no_line_but_a_state_is_confirmed_by_the_poll(scenario: Scenario) -> None:
    scenario.monkeypatch.setenv(RUN_MODE_ENV, RunMode.NO_LINE.value)

    scenario.tick_until("the entry to be resolved", scenario.resolved)

    entry = scenario.entry()
    assert entry.outcome is JournalOutcome.COMPLETED
    assert scenario.escalations() == [], "a state exists, so the launch is not overdue"


def test_a_late_line_goes_overdue_then_is_confirmed_recorded_and_closed(
    scenario: Scenario,
) -> None:
    scenario.monkeypatch.setenv(RUN_MODE_ENV, RunMode.LATE_LINE.value)
    scenario.monkeypatch.setenv(RUN_LATE_SECONDS_ENV, "2.0")

    scenario.tick_until(
        "a launch_overdue escalation",
        lambda: "launch_overdue" in scenario.escalations(),
    )
    assert not scenario.entry().is_resolved, "an overdue launch is left unresolved"

    scenario.tick_until("the entry to be resolved", scenario.resolved)
    scenario.tick_until("the escalation to close", lambda: scenario.escalations() == [])

    assert scenario.entry().outcome is JournalOutcome.COMPLETED


def test_a_usage_error_blocks_the_node_fails_the_entry_and_raises_upstream_shape(
    scenario: Scenario,
) -> None:
    scenario.monkeypatch.setenv(RUN_MODE_ENV, RunMode.USAGE_ERROR.value)

    with pytest.raises(UpstreamShapeError, match="--run-id"):
        scenario.tick_until("the shape error", lambda: False)

    entry = scenario.entry()
    assert entry.outcome is JournalOutcome.FAILED
    assert entry.result is not None and entry.result["launch_failure"] == "usage_error"
    assert scenario.store.blocked_state_for(scenario.node.id) is not None


def test_the_shape_error_exits_fifteen_through_the_cli_boundary(
    scenario: Scenario,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from amoeba.cli import main as cli_main

    def boom(_args: object) -> object:
        scenario.monkeypatch.setenv(RUN_MODE_ENV, RunMode.USAGE_ERROR.value)
        scenario.tick_until("the shape error", lambda: False)

    monkeypatch.setattr(cli_main, "_dispatch", boom)

    assert cli_main.main(["status"]) == cli_main.ExitCode.UPSTREAM_SHAPE == 15
    assert "--run-id" in capsys.readouterr().err
