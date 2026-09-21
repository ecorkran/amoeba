"""Tests for the resident host loop, with real subprocesses and real signals.

**Nothing here is mocked.** Signal handling and process lifetime are platform
behavior; a mocked signal would prove only that the mock works. Every test
drives a real ``ResidentProcess`` in a real subprocess via the shared harness
in ``host_harness.py`` — the same harness the load tier uses.

The seam proved here is the one slices 103 and 120 build on: a ``Tenant``
defined in a test is ticked by the real host, writes through ``store_for()``,
observes ``stop_requested``, and the process exits cleanly.
"""

from __future__ import annotations

import signal
import textwrap
import time
from pathlib import Path

import pytest
from host_harness import (
    HANGING_TENANT,
    RECORDING_TENANT,
    STOPPED_MARKER,
    HostProcess,
    TenantSpec,
    start_host,
)

from amoeba.process.errors import GraceExpiredError, StartupFailedError
from amoeba.process.host import ResidentProcess
from amoeba.process.settings import ProcessSettings
from amoeba.store import CommandKind, NodeKind, NodeStatus, Store

PROJECT = "demo"


@pytest.fixture
def supervisor_dir(tmp_path: Path) -> Path:
    """A throwaway supervisor directory. Never the real one."""
    directory = tmp_path / "supervisor"
    directory.mkdir()
    return directory


@pytest.fixture
def runs_dir(tmp_path: Path) -> Path:
    """An empty Squadron runs directory. Never the real one."""
    directory = tmp_path / "runs"
    directory.mkdir()
    return directory


def _seed_project(supervisor_dir: Path, project_id: str = PROJECT) -> Path:
    """Create a store for a project, as slice 101 code would leave it."""
    path = supervisor_dir / f"{project_id}.sqlite3"
    with Store.open(path) as store:
        store.create_node(project_id=project_id, kind=NodeKind.SLICE, title="seeded")
    return path


def _running_host(
    tmp_path: Path, supervisor_dir: Path, **kwargs: object
) -> HostProcess:
    """Start a host and wait for it to report readiness."""
    host = start_host(tmp_path, supervisor_dir, **kwargs)  # pyright: ignore[reportArgumentType]
    host.await_ready()
    return host


# --------------------------------------------------------------------------
# Zero tenants: this slice's working end state
# --------------------------------------------------------------------------


def test_zero_tenants_starts_recovers_idles_and_stops(
    tmp_path: Path, supervisor_dir: Path, runs_dir: Path
) -> None:
    """The end state slice 102 ships: a correct, idle, recoverable host."""
    _seed_project(supervisor_dir)
    host = _running_host(tmp_path, supervisor_dir, runs_dir=runs_dir)

    try:
        assert host.is_running()
        assert host.terminate_and_wait() == 0
        assert STOPPED_MARKER in host.remaining_stdout()
    finally:
        host.cleanup()


def test_an_empty_supervisor_directory_starts_and_stops(
    tmp_path: Path, supervisor_dir: Path, runs_dir: Path
) -> None:
    """A supervisor that has never run is a valid, empty state."""
    host = _running_host(tmp_path, supervisor_dir, runs_dir=runs_dir)

    try:
        assert host.terminate_and_wait() == 0
    finally:
        host.cleanup()


def test_sigterm_during_an_idle_wait_stops_promptly(
    tmp_path: Path, supervisor_dir: Path, runs_dir: Path
) -> None:
    """The idle path waits on the stop event, so stop is observed at once.

    The idle interval here is far longer than the time allowed for exit: a
    loop that slept instead of waiting on the event would miss the deadline.
    """
    _seed_project(supervisor_dir)
    host = _running_host(
        tmp_path, supervisor_dir, runs_dir=runs_dir, idle_interval_seconds=30.0
    )

    try:
        host.signal(signal.SIGTERM)
        assert host.wait(timeout=10.0) == 0
    finally:
        host.cleanup()


def test_sigint_also_stops_the_process(
    tmp_path: Path, supervisor_dir: Path, runs_dir: Path
) -> None:
    """Ctrl-C in the foreground is a clean stop, per D1."""
    _seed_project(supervisor_dir)
    host = _running_host(
        tmp_path, supervisor_dir, runs_dir=runs_dir, idle_interval_seconds=30.0
    )

    try:
        host.signal(signal.SIGINT)
        assert host.wait(timeout=10.0) == 0
    finally:
        host.cleanup()


# --------------------------------------------------------------------------
# The tenant seam
# --------------------------------------------------------------------------


def test_a_throwaway_tenant_is_ticked_and_its_writes_are_durable(
    tmp_path: Path, supervisor_dir: Path, runs_dir: Path
) -> None:
    """The Integration Requirement: the seam 103 and 120 will use.

    A tenant defined in this test is ticked by the real host, writes through
    ``store_for()``, and those writes survive the process exiting.
    """
    project_store_file = _seed_project(supervisor_dir)
    host = _running_host(
        tmp_path, supervisor_dir, runs_dir=runs_dir, tenant=RECORDING_TENANT
    )

    try:
        assert host.terminate_and_wait() == 0
    finally:
        host.cleanup()

    with Store.open_read_only(project_store_file) as store:
        titles = {node.title for node in store.nodes_for_project(PROJECT)}

    assert "seeded" in titles
    assert any(title.startswith("tick-") for title in titles), (
        f"the tenant never wrote through store_for(); saw {titles}"
    )


def test_a_tenant_observes_stop_requested(
    tmp_path: Path, supervisor_dir: Path, runs_dir: Path
) -> None:
    """A tenant polling ``stop_requested`` sees it flip, and exits its own work."""
    _seed_project(supervisor_dir)
    polling_tenant = TenantSpec(
        name="poller",
        body=textwrap.dedent(
            """
            import time as _time
            # A long operation that polls, as the contract requires.
            for _ in range(600):
                if host.stop_requested:
                    for project_id in host.project_ids:
                        host.store_for(project_id).create_node(
                            project_id=project_id,
                            kind=NodeKind.GATE,
                            title="saw-stop",
                        )
                    return True
                _time.sleep(0.01)
            return True
            """
        ).strip(),
    )
    host = _running_host(
        tmp_path, supervisor_dir, runs_dir=runs_dir, tenant=polling_tenant
    )

    try:
        assert host.terminate_and_wait() == 0
    finally:
        host.cleanup()

    with Store.open_read_only(supervisor_dir / f"{PROJECT}.sqlite3") as store:
        titles = {node.title for node in store.nodes_for_project(PROJECT)}

    assert "saw-stop" in titles, "the tenant never observed stop_requested"


def test_a_hanging_tenant_triggers_grace_expiry_and_names_it(
    tmp_path: Path, supervisor_dir: Path, runs_dir: Path
) -> None:
    """A tenant that ignores ``stop_requested`` ends in grace expiry.

    Asserted here as the host's own signal — a raised ``GraceExpiredError``,
    not an exit code. Task 7.3 separately proves this surfaces through the CLI
    as ``ExitCode.GRACE_EXPIRED``.

    Crucially, the process still **exits** rather than hanging the suite: the
    tenant is abandoned in place, never interrupted.
    """
    _seed_project(supervisor_dir)
    host = _running_host(
        tmp_path,
        supervisor_dir,
        runs_dir=runs_dir,
        tenant=HANGING_TENANT,
        shutdown_grace_seconds=1.0,
    )

    try:
        host.signal(signal.SIGTERM)
        returncode = host.wait(timeout=30.0)
    finally:
        host.cleanup()

    assert returncode != 0, "grace expiry is a failure exit, not a clean one"

    stdout = host.remaining_stdout()
    stderr = host.stderr_text()

    # The abandon path exits the process outright rather than unwinding — the
    # loop thread is stuck inside the tenant and is not coming back — so the
    # bootstrap's own handler never runs and no STOPPED marker is printed.
    assert STOPPED_MARKER not in stdout
    assert "grace period" in stderr, (
        f"expected the grace-expiry ERROR log; saw {stderr!r}"
    )
    assert HANGING_TENANT.name in stderr, (
        "the ERROR log must name the tenant that did not return"
    )


def test_grace_expiry_raises_the_typed_error_in_process(
    tmp_path: Path, supervisor_dir: Path, runs_dir: Path
) -> None:
    """The host's own signal for grace expiry is a typed error, not an exit code.

    Asserted in-process, where the abandon path is not taken: the tenant here
    returns just after the grace period rather than never, so ``run()`` unwinds
    normally and raises. Task 7.3 proves the subprocess case surfaces as
    ``ExitCode.GRACE_EXPIRED`` through the CLI.
    """
    _seed_project(supervisor_dir)

    class SlowTenant:
        name = "slowpoke"

        def __init__(self) -> None:
            self.ticked = False

        def tick(self, host: ResidentProcess) -> bool:
            if self.ticked:
                return False
            self.ticked = True
            host.request_stop()
            # Outlasts the grace period, ignoring stop_requested.
            time.sleep(1.5)
            return True

    process = ResidentProcess(
        ProcessSettings(
            idle_interval_seconds=0.01,
            shutdown_grace_seconds=0.2,
            sq_runs_dir=runs_dir,
        ),
        store_dir=supervisor_dir,
        version="test",
        tenants=(SlowTenant(),),
    )

    with pytest.raises(GraceExpiredError) as caught:
        process.run()

    assert caught.value.tenant_name == "slowpoke"


def test_tenants_tick_in_registration_order(
    tmp_path: Path, supervisor_dir: Path, runs_dir: Path
) -> None:
    """Registration order is the tick order, in-process.

    The *last* tenant requests the stop, so a full round completes before the
    loop ends. Stopping from an earlier tenant would legitimately skip the
    ones after it — the loop stops ticking new work as soon as the event is
    set, which is the documented shutdown behavior rather than an ordering
    violation.
    """
    _seed_project(supervisor_dir)
    ticks: list[str] = []

    class Recorder:
        def __init__(self, name: str, *, stop_after: bool = False) -> None:
            self.name = name
            self._stop_after = stop_after

        def tick(self, host: ResidentProcess) -> bool:
            ticks.append(self.name)
            if self._stop_after:
                host.request_stop()
            return False

    process = ResidentProcess(
        ProcessSettings(idle_interval_seconds=0.01, sq_runs_dir=runs_dir),
        store_dir=supervisor_dir,
        version="test",
        tenants=(Recorder("first"), Recorder("second", stop_after=True)),
    )
    process.run()

    assert ticks == ["first", "second"]


def test_a_stop_mid_round_skips_the_remaining_tenants(
    tmp_path: Path, supervisor_dir: Path, runs_dir: Path
) -> None:
    """Stop ticking new work as soon as the event is set.

    The grace period bounds only the tick already in progress; tenants that
    have not started this round are simply not ticked.
    """
    _seed_project(supervisor_dir)
    ticks: list[str] = []

    class Stopper:
        name = "stopper"

        def tick(self, host: ResidentProcess) -> bool:
            ticks.append(self.name)
            host.request_stop()
            return False

    class Later:
        name = "later"

        def tick(self, host: ResidentProcess) -> bool:
            ticks.append(self.name)
            return False

    process = ResidentProcess(
        ProcessSettings(idle_interval_seconds=0.01, sq_runs_dir=runs_dir),
        store_dir=supervisor_dir,
        version="test",
        tenants=(Stopper(), Later()),
    )
    process.run()

    assert ticks == ["stopper"]


# --------------------------------------------------------------------------
# Recovery gates the loop
# --------------------------------------------------------------------------


def test_no_tenant_ticks_before_recovery_completes(
    tmp_path: Path, supervisor_dir: Path, runs_dir: Path
) -> None:
    """Recovery gates startup: the journal is settled before the first tick.

    A node with an unresolved entry is escalated by recovery. The tenant
    records what it sees on its very first tick; if it ticked before recovery,
    it would see an unresolved entry.
    """
    project_store_file = _seed_project(supervisor_dir)
    with Store.open(project_store_file) as store:
        node = store.create_node(
            project_id=PROJECT, kind=NodeKind.SLICE, title="in-flight"
        )
        store.journal_issue(
            node.id,
            kind=CommandKind.SQ_RUN,
            parameters={"pipeline": "p6", "params": {"slice": "102"}},
        )

    first_tick_tenant = TenantSpec(
        name="observer",
        body=textwrap.dedent(
            """
            if self.ticks == 0:
                for project_id in host.project_ids:
                    store = host.store_for(project_id)
                    unresolved = store.unresolved_journal_entries(project_id)
                    store.create_node(
                        project_id=project_id,
                        kind=NodeKind.GATE,
                        title=f"unresolved-at-first-tick={len(unresolved)}",
                    )
            self.ticks += 1
            return False
            """
        ).strip(),
    )

    host = _running_host(
        tmp_path, supervisor_dir, runs_dir=runs_dir, tenant=first_tick_tenant
    )
    try:
        assert host.terminate_and_wait() == 0
    finally:
        host.cleanup()

    with Store.open_read_only(project_store_file) as store:
        titles = {node.title for node in store.nodes_for_project(PROJECT)}

    assert "unresolved-at-first-tick=0" in titles, (
        f"a tenant ticked before recovery finished; saw {titles}"
    )


def test_recovery_escalates_an_unresolved_entry_before_the_loop(
    tmp_path: Path, supervisor_dir: Path, runs_dir: Path
) -> None:
    """The startup recovery pass really reconciles, against an empty runs dir.

    Zero candidate runs means the entry escalates and the node blocks — the
    honest answer, not a guess.
    """
    project_store_file = _seed_project(supervisor_dir)
    with Store.open(project_store_file) as store:
        node = store.create_node(
            project_id=PROJECT, kind=NodeKind.SLICE, title="in-flight"
        )
        entry = store.journal_issue(
            node.id,
            kind=CommandKind.SQ_RUN,
            parameters={"pipeline": "p6", "params": {"slice": "102"}},
        )

    host = _running_host(tmp_path, supervisor_dir, runs_dir=runs_dir)
    try:
        assert host.terminate_and_wait() == 0
    finally:
        host.cleanup()

    with Store.open_read_only(project_store_file) as store:
        reloaded = store.journal_entry(entry.id)
        blocked_node = store.get_node(node.id)
        blocked_state = store.blocked_state_for(node.id)

    assert reloaded is not None and reloaded.is_resolved
    assert blocked_node is not None
    assert blocked_node.status is NodeStatus.BLOCKED_ON_HUMAN
    assert blocked_state is not None
    assert entry.id in blocked_state.context


def test_a_recovery_summary_is_logged_for_each_project(
    tmp_path: Path, supervisor_dir: Path, runs_dir: Path
) -> None:
    """Including 'nothing to reconcile', which is the common case."""
    _seed_project(supervisor_dir, "alpha")
    _seed_project(supervisor_dir, "beta")

    host = _running_host(tmp_path, supervisor_dir, runs_dir=runs_dir)
    try:
        assert host.terminate_and_wait() == 0
    finally:
        host.cleanup()

    stderr = host.stderr_text()

    assert "recovery alpha: nothing to reconcile" in stderr
    assert "recovery beta: nothing to reconcile" in stderr


def test_a_corrupt_store_aborts_startup_for_the_whole_supervisor(
    tmp_path: Path, supervisor_dir: Path, runs_dir: Path
) -> None:
    """One bad project stops the supervisor, deliberately.

    Running while blind to one project is worse than not running, so the
    failure propagates out of ``host.py`` rather than skipping the project.
    """
    _seed_project(supervisor_dir, "healthy")
    (supervisor_dir / "broken.sqlite3").write_bytes(b"this is not a sqlite database")

    process = ResidentProcess(
        ProcessSettings(idle_interval_seconds=0.01, sq_runs_dir=runs_dir),
        store_dir=supervisor_dir,
        version="test",
        tenants=(),
    )

    with pytest.raises(StartupFailedError, match="broken"):
        process.run()


def test_startup_failure_releases_the_lock(
    tmp_path: Path, supervisor_dir: Path, runs_dir: Path
) -> None:
    """A failed start leaves nothing held, so the next start is not blocked."""
    (supervisor_dir / "broken.sqlite3").write_bytes(b"not a database")
    settings = ProcessSettings(idle_interval_seconds=0.01, sq_runs_dir=runs_dir)

    with pytest.raises(StartupFailedError):
        ResidentProcess(settings, store_dir=supervisor_dir, version="test").run()

    # The lock is free, and the PID file was cleaned up.
    from amoeba.process.instance_lock import InstanceLock, lock_path

    lock = InstanceLock(lock_path({"AMOEBA_STORE_DIR": str(supervisor_dir)}))
    assert lock.held_by_another_process() is False
    assert not (supervisor_dir / "amoeba.pid").exists()


# --------------------------------------------------------------------------
# Single instance, and crash-only
# --------------------------------------------------------------------------


def test_a_second_host_refuses_and_does_not_disturb_the_first(
    tmp_path: Path, supervisor_dir: Path, runs_dir: Path
) -> None:
    """Single-instance enforcement at the process level."""
    _seed_project(supervisor_dir)
    first = _running_host(tmp_path, supervisor_dir, runs_dir=runs_dir)

    try:
        second = start_host(
            tmp_path, supervisor_dir, runs_dir=runs_dir, script_name="second.py"
        )
        try:
            assert second.wait(timeout=20.0) != 0
            assert "AlreadyRunningError" in "\n".join(second.remaining_stdout())
        finally:
            second.cleanup()

        # The first is untouched.
        assert first.is_running()
        assert first.terminate_and_wait() == 0
    finally:
        first.cleanup()


def test_the_pid_file_is_removed_on_a_clean_stop(
    tmp_path: Path, supervisor_dir: Path, runs_dir: Path
) -> None:
    """The normal path cleans up after itself."""
    _seed_project(supervisor_dir)
    host = _running_host(tmp_path, supervisor_dir, runs_dir=runs_dir)
    pid_file = supervisor_dir / "amoeba.pid"

    try:
        assert pid_file.exists(), "the pid file is written while running"
        assert host.terminate_and_wait() == 0
    finally:
        host.cleanup()

    assert not pid_file.exists()


def test_after_sigkill_a_new_host_starts_with_no_cleanup(
    tmp_path: Path, supervisor_dir: Path, runs_dir: Path
) -> None:
    """Crash-only, end to end: kill -9 then start, with no manual cleanup.

    The killed process leaves its PID file behind — nothing ran to remove it —
    and the next start succeeds anyway, because the lock is what matters.
    """
    _seed_project(supervisor_dir)
    victim = _running_host(tmp_path, supervisor_dir, runs_dir=runs_dir)
    victim.kill_and_wait()

    assert (supervisor_dir / "amoeba.pid").exists(), (
        "a killed process cleans up nothing"
    )

    survivor = _running_host(
        tmp_path, supervisor_dir, runs_dir=runs_dir, script_name="survivor.py"
    )
    try:
        assert survivor.is_running()
        assert survivor.terminate_and_wait() == 0
    finally:
        survivor.cleanup()


def test_committed_writes_survive_a_sigkill(
    tmp_path: Path, supervisor_dir: Path, runs_dir: Path
) -> None:
    """Committed state is not lost when the process is killed outright."""
    project_store_file = _seed_project(supervisor_dir)
    host = _running_host(
        tmp_path, supervisor_dir, runs_dir=runs_dir, tenant=RECORDING_TENANT
    )

    # The host is already past readiness; give the tenant a moment to tick
    # before the kill, so there is committed work to survive it.
    time.sleep(0.5)
    host.kill_and_wait()

    with Store.open_read_only(project_store_file) as store:
        titles = {node.title for node in store.nodes_for_project(PROJECT)}

    assert "seeded" in titles
    assert any(title.startswith("tick-") for title in titles)
