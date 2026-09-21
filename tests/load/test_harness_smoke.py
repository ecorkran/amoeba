"""The harness works from this tier — proven here, not deferred to 9.2.

Task 9.1's success criterion is that the shared process harness really starts a
subprocess running ``ResidentProcess`` with a throwaway tenant, and can signal
and wait on it. That is asserted here rather than taken on faith while the
substantive load tests are written.
"""

from __future__ import annotations

from pathlib import Path

from host_harness import start_host
from load_harness import JOURNALING_TENANT, PROJECT, seed_project

from amoeba.store import Store


def test_the_harness_starts_signals_and_stops_a_real_process(
    tmp_path: Path, supervisor_dir: Path, runs_dir: Path
) -> None:
    """A real subprocess, a real tenant, a real signal, a clean exit."""
    seed_project(supervisor_dir)

    host = start_host(
        tmp_path,
        supervisor_dir,
        tenant=JOURNALING_TENANT,
        runs_dir=runs_dir,
        idle_interval_seconds=0.02,
    )
    try:
        host.await_ready()
        assert host.is_running()
        assert host.terminate_and_wait() == 0
    finally:
        host.cleanup()

    # The tenant really ran and really wrote through store_for().
    with Store.open_read_only(supervisor_dir / f"{PROJECT}.sqlite3") as store:
        titles = {node.title for node in store.nodes_for_project(PROJECT)}
        entries = store.journal_entries(PROJECT)

    assert any(title.startswith("work-") for title in titles), (
        f"the journaling tenant never ticked; saw {titles}"
    )
    assert entries, "the tenant never journaled an entry"


def test_the_harness_survives_a_kill(
    tmp_path: Path, supervisor_dir: Path, runs_dir: Path
) -> None:
    """SIGKILL is available to the tier, and committed state survives it."""
    seed_project(supervisor_dir)

    host = start_host(
        tmp_path,
        supervisor_dir,
        tenant=JOURNALING_TENANT,
        runs_dir=runs_dir,
        idle_interval_seconds=0.02,
        script_name="killed.py",
    )
    try:
        host.await_ready()
        host.kill_and_wait()
    finally:
        host.cleanup()

    with Store.open_read_only(supervisor_dir / f"{PROJECT}.sqlite3") as store:
        # The seeded root node is committed and therefore survives, whatever
        # the tenant had in flight.
        assert store.nodes_for_project(PROJECT)
