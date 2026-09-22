"""The resident process: lifetime, the tenant seam, and graceful shutdown.

One long-lived process per supervisor. It acquires the instance lock, writes
the PID file, opens every project store **read-write** through
``ProjectStores`` — the only module permitted to do so, which
``tests/test_writer_guard.py`` enforces mechanically — reconciles every
journaled-but-unresolved command, then ticks its tenants until stop is
requested.

**Recovery gates the loop.** No tenant ticks until every project has been
reconciled, so the Runner can never act on a node whose in-flight command has
not been accounted for.

**The loop is synchronous (D2).** A tenant that launches a long subprocess polls
it and checks ``stop_requested``; it does not block the loop invisibly. There is
**by decision no per-tick timeout** and no watchdog: a synchronous loop cannot
interrupt a tenant that does not return without threads or signals whose failure
modes are worse than the one they fix. The obligation therefore sits on the
tenant, and ``docs/process-contract.md`` states it as a requirement. The
observable consequence is bounded and named: the grace period expires, the
process exits, and ``stop`` reports a timeout.

This module raises typed lifecycle errors and **never references ``ExitCode``**
— mapping a failure to an exit status is the CLI's job, at the process
boundary.
"""

from __future__ import annotations

import logging
import os
import signal
import sys
import threading
from collections.abc import Sequence
from pathlib import Path
from types import FrameType
from typing import Protocol

from amoeba.process.errors import (
    AlreadyRunningError,
    GraceExpiredError,
    StartupFailedError,
)
from amoeba.process.instance_lock import (
    InstanceLock,
    lock_path,
    pid_file_path,
    write_pid_file,
)
from amoeba.process.project_stores import ProjectStores
from amoeba.process.recovery import RecoverySummary, reconcile
from amoeba.process.settings import ProcessSettings
from amoeba.process.supervisor import build_observer_registry
from amoeba.store import Store

logger = logging.getLogger(__name__)

#: Recorded as the current tenant when no tick is in flight. Named rather than
#: an empty string so a grace-expiry log line is readable either way.
_NO_TENANT = "(no tenant)"

#: Fallback status for the abandon path when no caller supplied one. The CLI
#: passes ``ExitCode.GRACE_EXPIRED``; this is only what a direct, non-CLI
#: construction gets, and is deliberately a plain non-zero rather than a
#: member of a vocabulary this module is not allowed to know.
_DEFAULT_GRACE_EXPIRED_STATUS = 1


class Tenant(Protocol):
    """Something the resident process hosts. Exactly two members.

    ``tick`` **must** return promptly and poll ``host.stop_requested`` inside
    any long operation. This is a requirement, not a suggestion: there is no
    per-tick timeout, so a tenant that does not return holds the process until
    the grace period expires.
    """

    @property
    def name(self) -> str:
        """Identifies the tenant in logs, including the grace-expiry ERROR."""
        ...

    def tick(self, host: ResidentProcess) -> bool:
        """Do a unit of work. Returns whether any work was done."""
        ...


class ResidentProcess:
    """The process lifetime: lock, recover, tick, and shut down cleanly."""

    def __init__(
        self,
        settings: ProcessSettings,
        *,
        store_dir: Path,
        version: str,
        tenants: Sequence[Tenant] = (),
        grace_expired_exit_status: int = _DEFAULT_GRACE_EXPIRED_STATUS,
        exit_on_grace_expiry: bool = False,
    ) -> None:
        """Build a resident process. Nothing is acquired until :meth:`run`.

        Args:
            settings: Every tunable, per ``ProcessSettings``.
            store_dir: The supervisor directory holding stores, the lock, and
                the PID file.
            version: Recorded in the PID file. Informational.
            tenants: Ticked in registration order. **Zero tenants is the
                correct end state for slice 102**: the process starts,
                recovers, idles, and stops.
            grace_expired_exit_status: The status to exit with when a tenant
                must be abandoned after the grace period. Supplied by the CLI,
                which owns the exit-code vocabulary; this module names none.
            exit_on_grace_expiry: When true, a tenant that outlives the grace
                period causes the process to exit immediately rather than
                waiting for it. The CLI sets this, because otherwise a tenant
                that never returns holds the process forever. An in-process
                caller leaves it false and receives ``GraceExpiredError``
                once the tenant does return.
        """
        self._settings = settings
        self._store_dir = store_dir
        self._version = version
        self._tenants = tuple(tenants)
        self._grace_expired_exit_status = grace_expired_exit_status
        self._exit_on_grace_expiry = exit_on_grace_expiry
        self._stop_event = threading.Event()
        self._stores = ProjectStores(store_dir)
        self._current_tenant_name = _NO_TENANT
        self._lock = InstanceLock(lock_path({"AMOEBA_STORE_DIR": str(store_dir)}))

    @property
    def stop_requested(self) -> bool:
        """Whether shutdown has been requested. Tenants must poll this."""
        return self._stop_event.is_set()

    @property
    def settings(self) -> ProcessSettings:
        """The tunables this process was built with."""
        return self._settings

    @property
    def tenants(self) -> tuple[Tenant, ...]:
        """The registered tenants, in tick order."""
        return self._tenants

    def store_for(self, project_id: str) -> Store:
        """The open read-write store for a project.

        Raises:
            KeyError: If the project has no store open, which means it did not
                exist in the supervisor directory when the process started.
        """
        return self._stores.store_for(project_id)

    @property
    def project_ids(self) -> tuple[str, ...]:
        """The projects this process has open."""
        return self._stores.project_ids

    def request_stop(self) -> None:
        """Ask the loop to stop. Safe to call from a signal handler."""
        self._stop_event.set()

    def run(self) -> None:
        """Run the process to completion: the whole lifetime, in order.

        Raises:
            AlreadyRunningError: If another process holds the instance lock.
                Nothing is disturbed.
            StartupFailedError: If a store cannot be opened or recovery cannot
                complete for any project. The loop is never entered.
            GraceExpiredError: If a tenant does not return within the grace
                period during shutdown.
        """
        if not self._lock.acquire():
            raise AlreadyRunningError(f"another amoeba process holds {self._lock.path}")

        pid_path = pid_file_path({"AMOEBA_STORE_DIR": str(self._store_dir)})
        try:
            # The lock is acquired before the PID file is written, so a live
            # process can legitimately hold the lock with no PID file yet.
            write_pid_file(pid_path, version=self._version)
            self._stores.open_all()
            self._recover_every_project()
            self._run_loop_with_grace()
        finally:
            self._stores.close_all()
            pid_path.unlink(missing_ok=True)
            self._lock.release()

    def _run_loop_with_grace(self) -> None:
        """Run the loop on **this** thread, with a watchdog bounding shutdown.

        The loop stays on the calling thread because the stores live there:
        ``sqlite3`` connections may only be used by the thread that created
        them, so moving the loop off this thread would move every tenant write
        off it too.

        The grace period is instead enforced by a watchdog thread that owns no
        store and only observes. It starts when stop is requested and, if the
        loop has not returned by the time the grace period expires, logs at
        ERROR naming the tenant. A tenant mid-tick is **abandoned in place**,
        never interrupted — safe precisely because of crash-only: an abandoned
        tick is indistinguishable from ``kill -9`` and is reconciled by the
        same recovery path on the next start.

        What happens next depends on ``exit_on_grace_expiry``. The CLI sets it,
        because a tenant that never returns would otherwise hold the process
        forever and the operator's only remedy would be an external kill. A
        caller that drives the host in-process leaves it unset and gets the
        typed error once the tenant finally does return.

        Raises:
            GraceExpiredError: If the grace period expired before the loop
                returned.
        """
        expired = threading.Event()
        finished = threading.Event()

        def _watch() -> None:
            # Wait for shutdown to begin; nothing is bounded before that,
            # because there is no per-tick timeout by decision.
            while not self._stop_event.wait(timeout=0.05):
                if finished.is_set():
                    return

            if finished.wait(timeout=self._settings.shutdown_grace_seconds):
                return

            expired.set()
            logger.error(
                "tenant %r did not return within the %ss grace period; abandoning it",
                self._current_tenant_name,
                self._settings.shutdown_grace_seconds,
            )
            if self._exit_on_grace_expiry:
                self._abandon()

        watchdog = threading.Thread(target=_watch, name="amoeba-grace", daemon=True)
        watchdog.start()
        try:
            self._loop()
        finally:
            finished.set()

        if expired.is_set():
            raise GraceExpiredError(self._current_tenant_name)

    def _abandon(self) -> None:
        """Exit the process immediately, abandoning a tenant that will not return.

        Called only from the watchdog, only after the grace period expired.
        ``os._exit`` is deliberate: the loop thread is stuck inside a tenant,
        so no orderly unwinding is possible from here, and any ``atexit`` or
        buffered-output handling would run against a thread that is not coming
        back. The lock is released by the kernel, and the PID file left behind
        is harmless because nothing trusts it — which is exactly the state a
        ``kill -9`` leaves, and the one the next start recovers from.

        The status is supplied by the caller through
        :attr:`grace_expired_exit_status`, so this module names no exit code of
        its own — mapping a lifecycle failure to a status is the CLI's job.
        """
        sys.stderr.flush()
        sys.stdout.flush()
        os._exit(self._grace_expired_exit_status)

    def install_signal_handlers(self) -> None:
        """Route SIGTERM and SIGINT to the stop event.

        The event is the single piece of state published across an execution
        boundary, and setting it is all the handler does — no I/O, no store
        access, nothing that could deadlock against the loop.
        """

        def _handle(signal_number: int, _frame: FrameType | None) -> None:
            logger.info(
                "received %s; requesting stop", signal.Signals(signal_number).name
            )
            self.request_stop()

        signal.signal(signal.SIGTERM, _handle)
        signal.signal(signal.SIGINT, _handle)

    def _recover_every_project(self) -> None:
        """Reconcile every project before any tenant ticks.

        Raises:
            StartupFailedError: If recovery fails for any project. The process
                does not enter the loop against unreconciled state.
        """
        for project_id, store in self._stores.items():
            try:
                summary = self._recover_project(project_id, store)
            except Exception as error:
                logger.exception("recovery failed for project %s", project_id)
                raise StartupFailedError(
                    f"recovery failed for project {project_id!r}: {error}"
                ) from error

            logger.info("recovery %s: %s", project_id, summary.describe())

    def _recover_project(self, project_id: str, store: Store) -> RecoverySummary:
        """Reconcile one project against a freshly assembled registry."""
        registry = build_observer_registry(
            self._settings, store.recorded_result_run_ids(project_id)
        )
        return reconcile(store, project_id, registry)

    def _loop(self) -> None:
        """Tick tenants until stop is requested.

        When no tenant reported work, wait on the stop event rather than
        sleeping: the wait ends the moment stop is requested, so shutdown is
        observed promptly instead of after a full idle interval.
        """
        while not self._stop_event.is_set():
            worked = self._tick_once()
            if not worked and not self._stop_event.is_set():
                self._stop_event.wait(self._settings.idle_interval_seconds)

    def _tick_once(self) -> bool:
        """Tick each tenant in registration order, honoring a stop mid-round.

        Returns:
            Whether any tenant reported doing work.
        """
        worked = False
        for tenant in self._tenants:
            if self._stop_event.is_set():
                # Stop ticking new work as soon as stop is requested; the grace
                # period bounds only a tick already in progress.
                break
            # Recorded before the call and deliberately left set afterward, so
            # that if the grace period expires the main thread can name the
            # tenant that was mid-tick. Written on the loop thread and read on
            # the main thread only after the join times out — by which point
            # the loop thread is stuck inside this call and the value is
            # stable.
            self._current_tenant_name = tenant.name
            worked = tenant.tick(self) or worked
        return worked
