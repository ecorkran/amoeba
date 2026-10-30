"""The Runner against the stub ``sq``, in process: a slice through ``p456``.

The tenant, the planners and the store are the production ones; ``sq`` and ``cf`` are
stubs on ``PATH`` and the checkout is a real git repository. One run-state script per
scenario (``tests/sq_stub_scripts.py``).
"""

from __future__ import annotations

import dataclasses
import json
import os
import time
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from cf_stub import LOG_ENV as CF_LOG_ENV
from sq_stub import (
    RUN_LATE_SECONDS_ENV,
    RUN_MODE_ENV,
    RUN_OUTCOME_ENV,
    RUN_SCRIPT_ENV,
    RUN_SECONDS_ENV,
    RunMode,
    write_run_script,
    write_sq_stub,
)
from sq_stub_resume import RESUME_ARGV_LOG_ENV
from sq_stub_scripts import RunScript, agent_question_run, empty_reviews

from amoeba.process import ProcessSettings, UpstreamShapeError
from amoeba.runner import RunnerTenant, runner_tenant
from amoeba.runner.ingest.record import (
    RESULT_OUTCOME,
    RESULT_RUN_ID,
    RESULT_STATUS,
    RESULT_VERDICT_IDS,
)
from amoeba.runner.launch import log_paths
from amoeba.store import (
    PARAM_RUN_ID,
    BlockedKind,
    BlockedState,
    CFReference,
    Channel,
    CommandKind,
    JournalEntry,
    JournalOutcome,
    Node,
    NodeKind,
    NodeStatus,
    Store,
)
from runner.dispatch.cf_world import CfWorld
from runner.gate_rig import rig_checkout
from runner.resolutions.resolution_support import resolve_block
from runner.tick_support import drive_project

PROJECT = "demo"
CF_PROJECT = "cf-a"
PIPELINE = "p456"
FIRST_SLICE, SECOND_SLICE = 125, 126
GRACE_SECONDS = 0.5
WAIT_SECONDS = 20.0

SETTINGS = ProcessSettings(
    launch_grace_seconds=GRACE_SECONDS,
    run_poll_interval_seconds=0.1,
    tick_deadline_seconds=5.0,
    tick_call_timeout_seconds=4.0,
    shutdown_grace_seconds=10.0,
)


class Host:
    stop_requested = False

    def __init__(self, store: Store) -> None:
        self._store = store
        self.project_ids = (PROJECT,)

    def store_for(self, project_id: str) -> Store:
        assert project_id == PROJECT
        return self._store


class Scenario:
    """One driven project: a clean checkout, a stub ``cf``, and slices to run."""

    def __init__(
        self,
        tmp_path: Path,
        store: Store,
        monkeypatch: pytest.MonkeyPatch,
        slices: int = 1,
    ):
        home = tmp_path / "home"
        home.mkdir()
        self.tmp_path = tmp_path
        self.supervisor_dir = tmp_path / "supervisor"
        monkeypatch.setenv("HOME", str(home))
        world = CfWorld(tmp_path / "world")
        rig_checkout(world.root)
        rig_checkout(world.second)
        bin_dir = write_sq_stub(tmp_path / "bin")
        monkeypatch.setenv(
            "PATH",
            os.pathsep.join([str(bin_dir), str(world.bin_dir), os.environ["PATH"]]),
        )
        monkeypatch.setenv(RUN_SECONDS_ENV, "0.2")
        self.monkeypatch = monkeypatch
        self.store = store
        self.host = Host(store)
        store.record_cf_snapshot(world.snapshot_input(PROJECT, CF_PROJECT))
        self.nodes = _slices(store, slices)
        self.node: Node = self.nodes[0]
        drive_project(store)
        config = tmp_path / "projects.yaml"
        config.write_text(f"projects:\n  {PROJECT}:\n    pipeline: {PIPELINE}\n")
        self.settings = dataclasses.replace(SETTINGS, project_config_path=config)
        self._tenant: RunnerTenant | None = None

    def script(self, script: RunScript, outcome: str | None = None) -> None:
        """Make every run end as ``script`` says, with ``outcome`` if given."""
        path = write_run_script(
            self.tmp_path / "run-script.json",
            files=script.files,
            document=script.document,
        )
        self.monkeypatch.setenv(RUN_SCRIPT_ENV, str(path))
        if outcome is not None:
            self.monkeypatch.setenv(RUN_OUTCOME_ENV, outcome)

    @property
    def tenant(self) -> RunnerTenant:
        if self._tenant is None:
            self._tenant = runner_tenant(self.settings, self.supervisor_dir)
        return self._tenant

    def tick_until(self, description: str, done: Callable[[], bool]) -> None:
        """Tick the Runner until ``done``; fail rather than hang."""
        deadline = time.monotonic() + WAIT_SECONDS
        while not done():
            if time.monotonic() >= deadline:
                raise AssertionError(f"timed out waiting for {description}")
            self.tenant.tick(self.host)
            time.sleep(0.05)

    def entries(self, node: Node | None = None) -> list[JournalEntry]:
        found = self.store.journal_entries(PROJECT, node_id=(node or self.node).id)
        return [e for e in found if e.kind is CommandKind.SQ_RUN]

    def entry(self) -> JournalEntry:
        [entry] = self.entries()
        return entry

    def resolved(self) -> bool:
        entries = self.entries()
        return len(entries) == 1 and entries[0].is_resolved

    def done(self, node: Node) -> bool:
        return self.status(node) is NodeStatus.DONE

    def blocked(self) -> BlockedState | None:
        return self.store.blocked_state_for(self.node.id)

    def status(self, node: Node | None = None) -> NodeStatus:
        found = self.store.get_node((node or self.node).id)
        assert found is not None
        return found.status

    def escalations(self) -> list[str]:
        return [
            m.fault_kind or "" for m in self.store.open_project_escalations(PROJECT)
        ]


def _slices(store: Store, count: int) -> list[Node]:
    """``count`` slices under one initiative, in CF index order from the first."""
    initiative = store.create_node(
        project_id=PROJECT,
        kind=NodeKind.INITIATIVE,
        title="initiative",
        cf=CFReference(project=CF_PROJECT, index=120),
    )
    return [
        store.create_node(
            project_id=PROJECT,
            kind=NodeKind.SLICE,
            title=f"slice {FIRST_SLICE + offset}",
            parent_id=initiative.id,
            cf=CFReference(project=CF_PROJECT, index=FIRST_SLICE + offset),
        )
        for offset in range(count)
    ]


@pytest.fixture
def scenario(
    tmp_path: Path, store: Store, monkeypatch: pytest.MonkeyPatch
) -> Iterator[Scenario]:
    yield Scenario(tmp_path, store, monkeypatch)


def test_the_normal_path_records_run_id_outcome_and_status(
    scenario: Scenario, tmp_path: Path
) -> None:
    cf_log = tmp_path / "cf.log"
    scenario.monkeypatch.setenv(CF_LOG_ENV, str(cf_log))
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
    cf_calls = cf_log.read_text().splitlines()
    assert any(call.startswith("config get ") for call in cf_calls), "the log works"
    assert [call for call in cf_calls if call.startswith("set ")] == [], "no cf set"


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


def test_a_completed_slice_is_followed_by_the_next_slice_launching(
    tmp_path: Path, store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    scenario = Scenario(tmp_path, store, monkeypatch, slices=2)
    first, second = scenario.nodes
    scenario.script(empty_reviews())

    scenario.tick_until(
        "the second slice to launch", lambda: bool(scenario.entries(second))
    )

    assert scenario.status(first) is NodeStatus.DONE
    [launched] = scenario.entries(second)
    assert launched.parameters["pipeline"] == PIPELINE
    assert launched.parameters["params"] == {"slice": str(SECOND_SLICE)}
    scenario.tick_until("the second slice to finish", lambda: scenario.done(second))
    assert scenario.escalations() == []


def test_an_agent_question_blocks_with_the_question_then_resumes_with_instructions(
    tmp_path: Path, store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    scenario = Scenario(tmp_path, store, monkeypatch)
    question = "Which slice should I design, 178 or 179?"
    instructions = 'Design 178.\nQuote: "go" \u2014 not 179.'
    argv_log = tmp_path / "resume-argv.jsonl"
    monkeypatch.setenv(RESUME_ARGV_LOG_ENV, str(argv_log))
    scenario.script(agent_question_run(question), outcome="paused")

    scenario.tick_until("the node to block", lambda: scenario.blocked() is not None)

    blocked = scenario.blocked()
    assert blocked is not None and blocked.kind is BlockedKind.HUMAN
    [message] = [
        m
        for m in store.messages(PROJECT, channel=Channel.ESCALATION)
        if m.blocked_state_id == blocked.id
    ]
    assert message.payload is not None
    assert message.payload["reason"] == "agent_question"
    assert message.payload["question"] == question

    scenario.script(empty_reviews())
    resolve_block(store, blocked.id, "resume", instructions)
    scenario.tick_until("the slice to finish", lambda: scenario.done(scenario.node))

    [resume_argv] = [json.loads(line) for line in argv_log.read_text().splitlines()]
    assert resume_argv[resume_argv.index("--instructions") + 1] == instructions
    assert scenario.escalations() == []
