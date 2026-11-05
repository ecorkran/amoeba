"""The program store at the host: absent, appearing at runtime, corrupt at start."""

from __future__ import annotations

import textwrap
import time
from pathlib import Path

import pytest
from cli_harness import run_cli
from host_harness import TenantSpec, start_host
from program_harness import program_payload

from amoeba.cli.main import ExitCode
from amoeba.inbox import submit_program
from amoeba.store import ProgramSubmissionKind
from amoeba.store.paths import program_store_path

#: Generous, like the other process tests: a loaded machine must not flake.
APPEAR_TIMEOUT_SECONDS = 20.0


@pytest.fixture
def supervisor_dir(tmp_path: Path) -> Path:
    """A throwaway supervisor directory that exists. Never the real one."""
    directory = tmp_path / "supervisor"
    directory.mkdir()
    return directory


def _observing_tenant(supervisor_dir: Path, log: Path) -> TenantSpec:
    """Drains the program inbox, and logs what ``host.program_store`` is each tick."""
    return TenantSpec(
        body=textwrap.dedent(
            f"""
            from pathlib import Path
            from amoeba.process.program_inbox_tenant import ProgramInboxTenant

            if not hasattr(self, "inner"):
                self.inner = ProgramInboxTenant(Path({str(supervisor_dir)!r}))
            worked = self.inner.tick(host)
            state = "none" if host.program_store is None else "open"
            with Path({str(log)!r}).open("a") as handle:
                handle.write(state + "\\n")
            return worked
            """
        ).strip(),
        name="observer",
    )


def _await_states(log: Path, wanted: str) -> list[str]:
    deadline = time.monotonic() + APPEAR_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        states = log.read_text().split() if log.exists() else []
        if wanted in states:
            return states
        time.sleep(0.05)
    raise AssertionError(f"the host never reported program_store {wanted!r}")


def test_the_property_is_none_with_no_store_then_the_open_store_after_a_drain(
    tmp_path: Path, supervisor_dir: Path
) -> None:
    log = tmp_path / "states.log"
    process = start_host(
        tmp_path, supervisor_dir, tenant=_observing_tenant(supervisor_dir, log)
    )
    try:
        process.await_ready()
        assert _await_states(log, "none")[0] == "none"
        assert not program_store_path(supervisor_dir).exists()

        submit_program(
            kind=ProgramSubmissionKind.REGISTER_PROGRAM,
            payload=program_payload(),
            submitted_by="tester",
            store_dir=supervisor_dir,
        )

        assert _await_states(log, "open")
        assert program_store_path(supervisor_dir).is_file()
    finally:
        process.terminate_and_wait()
        process.cleanup()


def test_a_corrupt_program_store_at_start_is_startup_failed_naming_it(
    supervisor_dir: Path, tmp_path: Path
) -> None:
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    path = program_store_path(supervisor_dir)
    path.parent.mkdir()
    path.write_bytes(b"junk, not a sqlite database")

    result = run_cli(
        ["start", "--sq-runs-dir", str(runs_dir), "--idle-interval", "0.05"],
        supervisor_dir,
    )

    assert result.returncode == ExitCode.STARTUP_FAILED
    assert "program store" in result.stderr
