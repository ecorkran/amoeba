"""Start, kill, restart and inspect the Runner's crash-proof process (slice 122).

Real everything: signals, the instance lock, SQLite and the detached stub ``sq``
children. Every wait is a predicate with a timeout, never a fixed sleep. The
process is started from ``runner.crash_entry`` with ``PYTHONPATH`` at ``tests/``,
a stub ``sq`` first on ``PATH`` and a temporary ``HOME``.
"""

from __future__ import annotations

import os
import signal
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from contract.launched import LaunchedProcess
from sq_stub import (
    LOG_ENV,
    RUN_OUTCOME_ENV,
    RUN_SCRIPT_ENV,
    RUN_SECONDS_ENV,
    write_sq_stub,
)

from amoeba.store import (
    BlockedState,
    JournalEntry,
    Node,
    Store,
    project_store_path,
)
from runner.crash_entry import CRASH_PROJECT, KILL_AT_ENV, KillPoint
from runner.dispatch.cf_world import CfWorld
from runner.gate_rig import rig_checkout
from runner.tick_support import drive_project, ready_slice

TESTS_DIR = Path(__file__).resolve().parent.parent
PROJECT = CRASH_PROJECT
WAIT_TIMEOUT_SECONDS = 30.0
POLL_INTERVAL_SECONDS = 0.05


class CrashProofFailure(AssertionError):
    """A wait timed out or the process misbehaved; the message carries its output."""


@dataclass(frozen=True)
class RunSettings:
    """How the stub ``sq`` behaves for the runs of one scenario."""

    run_seconds: float
    outcome: str = "completed"
    #: A stub run script (``sq_stub.write_run_script``): the run's review files.
    script: Path | None = None


class CrashHarness:
    """One scenario's directories, node ids and process lifecycle."""

    def __init__(
        self,
        tmp_path: Path,
        node_count: int = 1,
        slice_name: str | None = None,
        *,
        dispatch: bool = False,
    ) -> None:
        """``slice_name`` puts the one step under a slice of that name, so a review
        the run writes can be attributed to it. ``dispatch`` runs the real dispatch
        planner over a stub ``cf`` world instead of the proof planner."""
        self.tmp_path = tmp_path
        self.slice_name = slice_name
        self.dispatch = dispatch
        self.world = CfWorld(tmp_path / "world") if dispatch else None
        self.home = tmp_path / "home"
        self.supervisor_dir = tmp_path / "supervisor"
        self.checkout = tmp_path / "checkout"
        self.markers_dir = tmp_path / "markers"
        self.logs_dir = tmp_path / "logs"
        self.sq_log = tmp_path / "sq-calls.log"
        for directory in (
            self.home,
            self.supervisor_dir,
            self.checkout,
            self.markers_dir,
            self.logs_dir,
        ):
            directory.mkdir()
        if self.world is not None:
            # A clean git repository, as the pre-dispatch checks read it (slice 128).
            self.checkout = rig_checkout(self.world.root)
        self.stub_dir = write_sq_stub(tmp_path / "stub-bin")
        self._launched: list[LaunchedProcess] = []
        self.node_ids = self._create_nodes(node_count)

    def _create_nodes(self, count: int) -> list[str]:
        """Create the project and its test nodes before any process starts."""
        with Store.open(project_store_path(self.supervisor_dir, PROJECT)) as store:
            if self.world is not None:
                node = ready_slice(store, PROJECT, "dispatch-slice", slice_index=125)
                node_ids = [node.id]
                store.record_cf_snapshot(self.world.snapshot_input(PROJECT, "cf-a"))
            elif self.slice_name is not None:
                node_ids = [ready_slice(store, PROJECT, self.slice_name).id]
            else:
                node_ids = [ready_slice(store, PROJECT).id for _ in range(count)]
            drive_project(store, PROJECT)
            return node_ids

    # -- processes ------------------------------------------------------------

    def environment(
        self, run: RunSettings, kill_at: KillPoint | None
    ) -> dict[str, str]:
        environment = {
            "PATH": f"{self.stub_dir}{os.pathsep}{os.environ['PATH']}",
            "HOME": str(self.home),
            "AMOEBA_STORE_DIR": str(self.supervisor_dir),
            "PYTHONPATH": str(TESTS_DIR),
            "PYTHONUNBUFFERED": "1",
            LOG_ENV: str(self.sq_log),
            RUN_SECONDS_ENV: str(run.run_seconds),
            RUN_OUTCOME_ENV: run.outcome,
        }
        if run.script is not None:
            environment[RUN_SCRIPT_ENV] = str(run.script)
        if self.world is not None:
            environment["PATH"] = (
                f"{self.world.bin_dir}{os.pathsep}{environment['PATH']}"
            )
        if kill_at is not None:
            environment[KILL_AT_ENV] = kill_at.value
        return environment

    def start(
        self, run: RunSettings, kill_at: KillPoint | None = None
    ) -> LaunchedProcess:
        """Start the resident process and wait until it reports ready."""
        label = f"resident-{len(self._launched) + 1}"
        command = [
            sys.executable,
            "-m",
            "runner.crash_entry",
            "--supervisor-dir",
            str(self.supervisor_dir),
            "--checkout",
            str(self.checkout),
            "--markers-dir",
            str(self.markers_dir),
        ]
        for node_id in self.node_ids:
            command += ["--node-id", node_id]
        if self.dispatch:
            command.append("--dispatch")
        launched = LaunchedProcess(
            label,
            command,
            environment=self.environment(run, kill_at),
            working_dir=self.tmp_path,
            stderr_path=self.logs_dir / f"{label}.stderr.log",
        )
        self._launched.append(launched)
        if kill_at is None:
            self.wait_until(
                "the process to report ready",
                lambda: self._ready_or_dead(launched),
            )
        return launched

    def _ready_or_dead(self, launched: LaunchedProcess) -> bool:
        if launched.is_ready:
            return True
        if not launched.host.is_running():
            raise CrashProofFailure(f"{launched.label} exited before it was ready")
        return False

    def wait_for_sigkill(self, launched: LaunchedProcess) -> None:
        """Wait for the process to die, and require that it died by SIGKILL."""
        self.wait_until("the process to exit", lambda: not launched.host.is_running())
        if launched.host.returncode != -signal.SIGKILL:
            raise CrashProofFailure(
                f"expected SIGKILL, got exit {launched.host.returncode}"
                f"\n{self.captured_output()}"
            )

    def stop(self, launched: LaunchedProcess) -> None:
        """SIGTERM the process and wait for a clean exit."""
        launched.host.signal(signal.SIGTERM)
        self.wait_until("the process to exit", lambda: not launched.host.is_running())

    def close(self) -> None:
        for launched in self._launched:
            launched.close()

    # -- waiting and reading -------------------------------------------------------

    def wait_until(
        self,
        description: str,
        predicate: Callable[[], bool],
        *,
        timeout: float = WAIT_TIMEOUT_SECONDS,
    ) -> None:
        """Poll ``predicate``; fail with all captured output on timeout."""
        deadline = time.monotonic() + timeout
        while not predicate():
            if time.monotonic() >= deadline:
                raise CrashProofFailure(
                    f"timed out after {timeout}s waiting for {description}"
                    f"\n{self.captured_output()}"
                )
            time.sleep(POLL_INTERVAL_SECONDS)

    def captured_output(self) -> str:
        return "\n".join(launched.captured() for launched in self._launched)

    def entries(self) -> list[JournalEntry]:
        with Store.open_read_only(
            project_store_path(self.supervisor_dir, PROJECT)
        ) as store:
            return store.journal_entries(PROJECT)

    def wait_for_entries(self, count: int) -> list[JournalEntry]:
        self.wait_until(
            f"{count} journal entries", lambda: len(self.entries()) >= count
        )
        return self.entries()

    def wait_for_resolution(self) -> JournalEntry:
        """Wait until the one entry is resolved, and return it."""
        self.wait_until(
            "the journal entry to be resolved",
            lambda: len(self.entries()) == 1 and self.entries()[0].is_resolved,
        )
        return self.entries()[0]

    def open_blocks(self, node_id: str) -> list[BlockedState]:
        with Store.open_read_only(
            project_store_path(self.supervisor_dir, PROJECT)
        ) as store:
            return [s for s in store.all_blocked_states(node_id) if not s.is_resolved]

    def verdict_ids(self) -> list[str]:
        with Store.open_read_only(
            project_store_path(self.supervisor_dir, PROJECT)
        ) as store:
            return [verdict.id for verdict in store.verdicts(PROJECT)]

    def node(self, node_id: str) -> Node:
        with Store.open_read_only(
            project_store_path(self.supervisor_dir, PROJECT)
        ) as store:
            found = store.get_node(node_id)
        assert found is not None
        return found

    def sq_run_calls(self, run_id: str) -> int:
        """How many times the stub was asked to ``sq run`` this id."""
        if not self.sq_log.exists():
            return 0
        return sum(
            1
            for line in self.sq_log.read_text().splitlines()
            if line.startswith("run ") and f"--run-id {run_id}" in line
        )

    def all_sq_run_calls(self) -> int:
        if not self.sq_log.exists():
            return 0
        return sum(
            1
            for line in self.sq_log.read_text().splitlines()
            if line.startswith("run ")
        )
