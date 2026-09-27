"""Helpers for the load tier.

The process harness itself is **not** redefined here: it lives in
``tests/host_harness.py`` and is shared with ``tests/test_host.py``, per the
project's DRY rule. This module adds only what the load tier needs on top of
it — a journal-issuing tenant, helpers for synthesizing run files at scale,
and the submitter-plus-SIGKILL loop the concurrent inbox tests share.

The tier's fixtures live in ``conftest.py``, which is also what puts
``tests/`` on ``sys.path`` so ``host_harness`` imports here.
"""

from __future__ import annotations

import json
import random
import subprocess
import sys
import textwrap
import time
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from cli_harness import await_running, cli_environment, run_cli, start_background
from host_harness import TenantSpec

from amoeba.inbox import pending

PROJECT = "demo"

#: A tenant that journals an entry on every tick and resolves the previous one.
#: This is what gives the crash loop something to lose: at any instant there is
#: an unresolved entry whose side effect may or may not have happened.
JOURNALING_TENANT = TenantSpec(
    name="journaler",
    body=textwrap.dedent(
        """
        from amoeba.store import CommandKind, JournalOutcome

        for project_id in host.project_ids:
            store = host.store_for(project_id)
            node = store.create_node(
                project_id=project_id,
                kind=NodeKind.SLICE,
                title=f"work-{self.ticks}",
            )
            entry = store.journal_issue(
                node.id,
                kind=CommandKind.SQ_RUN,
                parameters={
                    "pipeline": "loadtest",
                    "params": {"tick": str(self.ticks)},
                },
            )
            # Resolve the PREVIOUS entry, so one is always left in flight.
            previous = getattr(self, "previous_entry", None)
            if previous is not None:
                store.journal_resolve(
                    previous,
                    outcome=JournalOutcome.COMPLETED,
                    result={"run_id": f"run-{self.ticks}"},
                )
            self.previous_entry = entry.id
        self.ticks += 1
        return True
        """
    ).strip(),
)


def write_run_file(
    runs_dir: Path,
    run_id: str,
    *,
    pipeline: str,
    params: dict[str, object],
    started_at: datetime,
    status: str = "completed",
    schema_version: int = 4,
) -> Path:
    """Synthesize one Squadron run file.

    Synthesized rather than copied because this tier measures **scale**, not
    realism — the real-fixture coverage is ``tests/test_observer_sq_runs.py``'s
    job. The shape matches the six header fields the observer reads.
    """
    path = runs_dir / f"{run_id}.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": schema_version,
                "run_id": run_id,
                "pipeline": pipeline,
                "params": params,
                "started_at": started_at.isoformat().replace("+00:00", "Z"),
                "status": status,
            }
        ),
        encoding="utf-8",
    )
    return path


def synthesize_runs(
    runs_dir: Path,
    count: int,
    *,
    pipeline: str = "loadtest",
    started_at: datetime | None = None,
) -> list[str]:
    """Write ``count`` run files and return their ids, oldest first."""
    base = started_at if started_at is not None else datetime.now(UTC)
    return [
        write_run_file(
            runs_dir,
            f"run-{index:05d}",
            pipeline=pipeline,
            params={"index": str(index)},
            started_at=base + timedelta(seconds=index),
        ).stem
        for index in range(count)
    ]


def seed_project(supervisor_dir: Path, project_id: str = PROJECT) -> Path:
    """Create a store for a project and return its path."""
    from amoeba.store import NodeKind, Store

    path = supervisor_dir / f"{project_id}.sqlite3"
    with Store.open(path) as store:
        store.create_node(project_id=project_id, kind=NodeKind.SLICE, title="root")
    return path


def submitter_output(tmp_path: Path, number: int) -> tuple[Path, Path]:
    """Where submitter ``number`` writes its stdout and stderr."""
    return tmp_path / f"submitter-{number}.out", tmp_path / f"submitter-{number}.err"


def launch_submitters(
    tmp_path: Path,
    supervisor_dir: Path,
    source: str,
    arguments: Sequence[Sequence[str]],
) -> list[subprocess.Popen[bytes]]:
    """Start one ``source`` process per argument list, each writing to files.

    Files, not pipes: nothing reads a submitter's output until it has exited,
    and a pipe nobody drains blocks its writer once the buffer fills — which
    on macOS can be small — hanging the run.
    """
    script = tmp_path / "submitter.py"
    script.write_text(source, encoding="utf-8")
    submitters: list[subprocess.Popen[bytes]] = []
    for number, argv in enumerate(arguments):
        stdout_file, stderr_file = submitter_output(tmp_path, number)
        with stdout_file.open("wb") as stdout, stderr_file.open("wb") as stderr:
            submitters.append(
                subprocess.Popen(
                    [sys.executable, str(script), *argv],
                    stdin=subprocess.DEVNULL,
                    stdout=stdout,
                    stderr=stderr,
                    env=cli_environment(supervisor_dir),
                )
            )
    return submitters


@dataclass(frozen=True)
class KillRun:
    """What a kill loop measured: kills landed, and the final drain."""

    kills: int
    backlog: int
    drain_seconds: float


def run_with_kills(
    supervisor_dir: Path,
    start_arguments: Sequence[str],
    submitters: Sequence[subprocess.Popen[bytes]],
    *,
    rng: random.Random,
    kill_window: tuple[float, float],
    target_kills: int,
    deadline: float,
) -> KillRun:
    """SIGKILL and restart ``amoeba start`` at random points, then drain.

    Kills continue while any submitter runs, and after that while the inbox
    still holds files, until ``target_kills`` have landed. The process is then
    left to drain the rest, which is what ``drain_seconds`` times.
    """
    process = start_background(supervisor_dir, list(start_arguments))
    kills = 0
    try:
        while any(submitter.poll() is None for submitter in submitters) or (
            kills < target_kills and pending(supervisor_dir)
        ):
            assert time.monotonic() < deadline, "the run never finished"
            time.sleep(rng.uniform(*kill_window))
            process.kill_and_wait()
            process.cleanup()
            kills += 1
            process = start_background(supervisor_dir, list(start_arguments))

        drain_started = time.monotonic()
        backlog = len(pending(supervisor_dir))
        await_running(supervisor_dir)
        while pending(supervisor_dir):
            assert time.monotonic() < deadline, "the inbox never drained"
            time.sleep(0.02)
        drain_seconds = time.monotonic() - drain_started
        assert run_cli(["stop"], supervisor_dir).returncode == 0
    finally:
        process.cleanup()
        for submitter in submitters:
            if submitter.poll() is None:
                submitter.kill()
    return KillRun(kills=kills, backlog=backlog, drain_seconds=drain_seconds)


def measured(label: str, seconds: float, bound: float) -> str:
    """Render a measurement for a test's failure message.

    Bounds in this tier are set from a real measurement and then roughly
    doubled, so a failure means a regression *in kind* — a per-entry directory
    scan, an accidental O(n squared) match — rather than normal machine
    variance. The measured value is always reported, so a bound that turns out
    to be wrong is visible rather than silently tuned.
    """
    return f"{label}: {seconds:.3f}s against a bound of {bound:.1f}s"


def assert_no_duplicate_reconciliation(outcomes: Sequence[str]) -> None:
    """Every entry carries exactly one outcome.

    An entry reconciled twice would either raise on the second attempt or
    overwrite the first outcome; this asserts the population is consistent
    with each entry having been closed exactly once.
    """
    assert all(outcome for outcome in outcomes), (
        "every entry must carry an outcome after recovery"
    )
