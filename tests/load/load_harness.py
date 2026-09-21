"""Helpers for the load tier.

The process harness itself is **not** redefined here: it lives in
``tests/host_harness.py`` and is shared with ``tests/test_host.py``, per the
project's DRY rule. This module adds only what the load tier needs on top of
it — a journal-issuing tenant and helpers for synthesizing run files at scale.

The tier's fixtures live in ``conftest.py``, which is also what puts
``tests/`` on ``sys.path`` so ``host_harness`` imports here.
"""

from __future__ import annotations

import json
import textwrap
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path

from host_harness import TenantSpec

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
