"""Shared harness for driving a real ``ResidentProcess`` in a subprocess.

Both ``test_host.py`` and the ``tests/load/`` tier need the same thing: a real
resident process, in a real subprocess, with a throwaway tenant registered,
that can be signalled and waited on. It is written once here rather than twice,
per the project's DRY rule.

The CLI deliberately ships no tenant registration — this slice ships no tenants
— so the harness writes a small bootstrap script that constructs
``ResidentProcess`` directly. That is a *test-only* seam, not a product
feature, which is why it lives under ``tests/`` rather than behind a CLI flag.

Nothing here mocks signals, locking, or process lifetime.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import textwrap
import time
from dataclasses import dataclass
from pathlib import Path

#: How long to wait for a subprocess to announce a state before giving up.
READY_TIMEOUT_SECONDS = 20.0

#: How long to wait for a process to exit after being signalled.
EXIT_TIMEOUT_SECONDS = 20.0

#: Printed by the bootstrap once the loop is running, so a test can wait for
#: readiness instead of sleeping.
READY_MARKER = "AMOEBA-READY"

#: Printed once run() returns normally.
STOPPED_MARKER = "AMOEBA-STOPPED"

#: Printed, with the exception type, when run() raises.
FAILED_MARKER = "AMOEBA-FAILED"


@dataclass(frozen=True)
class TenantSpec:
    """A throwaway tenant's source, injected into the bootstrap script.

    Args:
        body: The body of ``tick``, as source. It may use ``host`` and must
            return a bool. Written as a plain string so each test states the
            tenant behavior it needs without a new module per case.
        name: The tenant's name, which grace-expiry logs report.
    """

    body: str
    name: str = "throwaway"


#: A tenant that records each tick into its project's store and stops politely.
RECORDING_TENANT = TenantSpec(
    body=textwrap.dedent(
        """
        for project_id in host.project_ids:
            store = host.store_for(project_id)
            store.create_node(
                project_id=project_id,
                kind=NodeKind.SLICE,
                title=f"tick-{self.ticks}",
            )
        self.ticks += 1
        return False
        """
    ).strip(),
    name="recorder",
)

#: A tenant that ignores ``stop_requested`` entirely, to force grace expiry.
HANGING_TENANT = TenantSpec(
    body=textwrap.dedent(
        """
        import time as _time
        # Deliberately ignores host.stop_requested, violating the tenant
        # contract, so the grace period is what ends the process.
        _time.sleep(600)
        return True
        """
    ).strip(),
    name="hanger",
)


def _bootstrap_source(
    supervisor_dir: Path,
    runs_dir: Path,
    tenant: TenantSpec | None,
    *,
    idle_interval_seconds: float,
    shutdown_grace_seconds: float,
) -> str:
    """Render the program the subprocess runs."""
    tenant_class = ""
    tenant_argument = "()"
    if tenant is not None:
        # The tenant body is indented to sit inside ``tick``; the whole class
        # is assembled at column zero because it is interpolated into an
        # already-dedented template below.
        tenant_class = (
            "class ThrowawayTenant:\n"
            f"    name = {tenant.name!r}\n\n"
            "    def __init__(self):\n"
            "        self.ticks = 0\n\n"
            "    def tick(self, host):\n"
            f"{textwrap.indent(tenant.body, ' ' * 8)}\n"
        )
        tenant_argument = "(ThrowawayTenant(),)"

    # Dedented FIRST, then interpolated: interpolating a column-zero class into
    # an indented template would make dedent() a no-op and the result invalid.
    # UP032 (prefer an f-string) is suppressed deliberately — an f-string would
    # interpolate before dedent runs, which is exactly the bug this shape
    # avoids.
    template = textwrap.dedent(
        """
        import logging, sys
        from pathlib import Path

        from amoeba.process.host import ResidentProcess
        from amoeba.process.settings import ProcessSettings
        from amoeba.store import NodeKind

        logging.basicConfig(level=logging.INFO, stream=sys.stderr)

        __TENANT_CLASS__

        settings = ProcessSettings(
            idle_interval_seconds={idle_interval_seconds!r},
            shutdown_grace_seconds={shutdown_grace_seconds!r},
            sq_runs_dir=Path({runs_dir!r}),
        )
        process = ResidentProcess(
            settings,
            store_dir=Path({supervisor_dir!r}),
            version="test",
            tenants=__TENANT_ARGUMENT__,
            # As the CLI does: a tenant that never returns must not hold the
            # process forever.
            exit_on_grace_expiry=True,
        )
        process.install_signal_handlers()

        # Readiness is announced from inside the process, immediately after
        # recovery has completed for every project and before the first tick.
        # Wrapping _loop is what makes "ready" mean recovery-is-done rather
        # than merely "the interpreter started".
        _real_loop = process._loop

        def _announce_then_loop():
            print({ready!r}, flush=True)
            _real_loop()

        process._loop = _announce_then_loop

        try:
            process.run()
        except BaseException as error:
            print({failed!r} + " " + type(error).__name__, flush=True)
            raise
        print({stopped!r}, flush=True)
        """.format(  # noqa: UP032 - see the comment above; f-string breaks dedent
            idle_interval_seconds=idle_interval_seconds,
            shutdown_grace_seconds=shutdown_grace_seconds,
            runs_dir=str(runs_dir),
            supervisor_dir=str(supervisor_dir),
            ready=READY_MARKER,
            failed=FAILED_MARKER,
            stopped=STOPPED_MARKER,
        )
    )

    # The tenant class is substituted after dedent, at column zero.
    return template.replace("__TENANT_CLASS__", tenant_class).replace(
        "__TENANT_ARGUMENT__", tenant_argument
    )


class HostProcess:
    """A real resident process running in a subprocess."""

    def __init__(self, process: subprocess.Popen[str]) -> None:
        self._process = process
        self.stdout_lines: list[str] = []

    @property
    def pid(self) -> int:
        """The subprocess's pid."""
        return self._process.pid

    @property
    def returncode(self) -> int | None:
        """The exit status, or ``None`` while still running."""
        return self._process.returncode

    def is_running(self) -> bool:
        """Whether the process is still alive."""
        return self._process.poll() is None

    def await_line(self, marker: str, timeout: float = READY_TIMEOUT_SECONDS) -> str:
        """Read stdout until a line starting with ``marker`` arrives."""
        assert self._process.stdout is not None
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            line = self._process.stdout.readline()
            if not line:
                break
            stripped = line.strip()
            self.stdout_lines.append(stripped)
            if stripped.startswith(marker):
                return stripped
        raise AssertionError(
            f"did not see {marker!r} within {timeout}s; saw {self.stdout_lines}"
        )

    def await_ready(self) -> None:
        """Block until the process reports its loop is running."""
        self.await_line(READY_MARKER)

    def signal(self, signal_number: int) -> None:
        """Send a real signal to the real process."""
        os.kill(self._process.pid, signal_number)

    def terminate_and_wait(self, timeout: float = EXIT_TIMEOUT_SECONDS) -> int:
        """SIGTERM the process and wait for it to exit."""
        self.signal(signal.SIGTERM)
        return self.wait(timeout)

    def kill_and_wait(self, timeout: float = EXIT_TIMEOUT_SECONDS) -> int:
        """SIGKILL the process and wait, simulating a crash."""
        self.signal(signal.SIGKILL)
        return self.wait(timeout)

    def wait(self, timeout: float = EXIT_TIMEOUT_SECONDS) -> int:
        """Wait for exit and return the status."""
        return self._process.wait(timeout=timeout)

    def stderr_text(self) -> str:
        """Everything the process wrote to stderr, after it has exited."""
        assert self._process.stderr is not None
        return self._process.stderr.read()

    def remaining_stdout(self) -> list[str]:
        """Drain whatever stdout lines remain after exit."""
        assert self._process.stdout is not None
        for line in self._process.stdout:
            self.stdout_lines.append(line.strip())
        return self.stdout_lines

    def cleanup(self) -> None:
        """Make sure the process is gone, whatever the test did."""
        if self.is_running():
            self._process.kill()
            self._process.wait(timeout=EXIT_TIMEOUT_SECONDS)


def start_host(
    tmp_path: Path,
    supervisor_dir: Path,
    *,
    tenant: TenantSpec | None = None,
    runs_dir: Path | None = None,
    idle_interval_seconds: float = 0.05,
    shutdown_grace_seconds: float = 2.0,
    script_name: str = "bootstrap.py",
) -> HostProcess:
    """Launch a real resident process in a subprocess.

    Args:
        tmp_path: Where to write the bootstrap script.
        supervisor_dir: The supervisor directory. Always inside ``tmp_path`` in
            tests, so the real one is never touched.
        tenant: A throwaway tenant to register, or ``None`` for the
            zero-tenant case this slice ships.
        runs_dir: The Squadron runs directory the observer scans. Defaults to
            an empty directory inside ``tmp_path`` — never the real one.
        idle_interval_seconds: Short by default, so tests are quick.
        shutdown_grace_seconds: Short by default, so the grace-expiry test does
            not stall the suite.
        script_name: Lets one test launch several distinct processes.

    Returns:
        A handle for signalling and waiting on the process.
    """
    if runs_dir is None:
        runs_dir = tmp_path / "empty-runs"
        runs_dir.mkdir(exist_ok=True)

    script = tmp_path / script_name
    script.write_text(
        _bootstrap_source(
            supervisor_dir,
            runs_dir,
            tenant,
            idle_interval_seconds=idle_interval_seconds,
            shutdown_grace_seconds=shutdown_grace_seconds,
        ),
        encoding="utf-8",
    )

    return HostProcess(
        subprocess.Popen(
            [sys.executable, str(script)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    )
