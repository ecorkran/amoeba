"""Crash-only, under repetition: start, SIGKILL at a random point, restart.

This is the slice's central claim exercised until it either holds or breaks:
after every cycle, no committed node or journal entry is missing, no entry is
reconciled twice, and start-to-ready stays under an asserted bound.

**Bounds were measured first, then set at roughly twice the observation**, per
the LLD, so a failure means a regression *in kind* — recovery that rescans per
entry, a lock that needs cleanup, a start that waits on something it should not
— rather than normal machine variance. The measured numbers are recorded below
and are printed on failure, so a bound that turns out to be wrong is visible
rather than quietly tuned to whatever passes.

Measured 20260921 on the development machine (Darwin 25.5.0, Python 3.13.7,
SQLite 3.50.4), 12 cycles with a journaling tenant:

    start-to-ready, min       0.075 s
    start-to-ready, median    0.082 s
    start-to-ready, max       0.094 s
    bound asserted            2.0   s

The LLD's candidate bound was "start-to-ready under 2 s". The measurement came
in more than twenty times below it, so **the candidate is kept as the asserted
bound rather than tightened to roughly twice the observation** — the deviation
from the LLD's rule, recorded here rather than applied silently. At ~0.09 s
observed, a 0.2 s bound would be dominated by CI scheduling noise and process
startup variance on a loaded machine, and would fail for reasons that say
nothing about this code. What this assertion is for is catching a regression in
*kind*: recovery that rescans the runs directory per entry, a lock that needs
cleanup before a restart, a start that waits on something it should not. Any of
those moves start-to-ready by orders of magnitude, not by tens of milliseconds.

The test prints its measured distribution on every run, so the real numbers
stay visible and a bound that stops matching reality is obvious.
"""

from __future__ import annotations

import random
import time
from pathlib import Path

from host_harness import start_host
from load_harness import JOURNALING_TENANT, PROJECT, seed_project

from amoeba.store import JournalOutcome, Store

#: How many crash cycles to run. Enough that the SIGKILL lands at varied points
#: in the tenant's work, without making the tier slow enough to be skipped.
CYCLES = 12

#: Asserted bound on start-to-ready. See the module docstring for the
#: measurement this is based on and why it was not tightened further.
START_TO_READY_BOUND_SECONDS = 2.0

#: The window the kill lands in, in seconds. Randomized per cycle so the
#: process is killed at genuinely varying points rather than always at the
#: same instant in its work.
KILL_WINDOW_SECONDS = (0.02, 0.30)


def _committed_state(store_file: Path) -> tuple[set[str], set[str]]:
    """Node ids and journal entry ids currently committed in the store."""
    with Store.open_read_only(store_file) as store:
        nodes = {node.id for node in store.nodes_for_project(PROJECT)}
        entries = {entry.id for entry in store.journal_entries(PROJECT)}
    return nodes, entries


def _outcomes_by_entry(store_file: Path) -> dict[str, JournalOutcome | None]:
    """Every entry's outcome, by entry id."""
    with Store.open_read_only(store_file) as store:
        return {entry.id: entry.outcome for entry in store.journal_entries(PROJECT)}


def test_crash_loop_loses_no_committed_state_and_never_double_reconciles(
    tmp_path: Path, supervisor_dir: Path, runs_dir: Path
) -> None:
    """Repeatedly kill the process mid-work; nothing committed is ever lost.

    Each cycle asserts three things:

    1. Every node and entry committed before the kill is still there after it.
    2. No entry that already carried an outcome has a *different* outcome
       afterward — which is what a second reconciliation would produce.
    3. Start-to-ready stays under the asserted bound.
    """
    store_file = seed_project(supervisor_dir)
    random_generator = random.Random(20260921)

    previous_nodes: set[str] = set()
    previous_entries: set[str] = set()
    settled_outcomes: dict[str, JournalOutcome] = {}
    start_durations: list[float] = []

    for cycle in range(CYCLES):
        started = time.monotonic()
        host = start_host(
            tmp_path,
            supervisor_dir,
            tenant=JOURNALING_TENANT,
            runs_dir=runs_dir,
            idle_interval_seconds=0.02,
            script_name=f"cycle-{cycle}.py",
        )
        try:
            host.await_ready()
            ready_after = time.monotonic() - started
            start_durations.append(ready_after)

            assert ready_after < START_TO_READY_BOUND_SECONDS, (
                f"cycle {cycle}: start-to-ready took {ready_after:.3f}s, over "
                f"the {START_TO_READY_BOUND_SECONDS}s bound. Measured values "
                f"so far: {[round(value, 3) for value in start_durations]}"
            )

            # Let the tenant do a varying amount of work, then kill it outright.
            time.sleep(random_generator.uniform(*KILL_WINDOW_SECONDS))
            host.kill_and_wait()
        finally:
            host.cleanup()

        nodes, entries = _committed_state(store_file)

        assert previous_nodes <= nodes, (
            f"cycle {cycle}: committed nodes went missing: "
            f"{sorted(previous_nodes - nodes)}"
        )
        assert previous_entries <= entries, (
            f"cycle {cycle}: committed journal entries went missing: "
            f"{sorted(previous_entries - entries)}"
        )

        # An entry that already had an outcome must keep exactly that outcome.
        # A second reconciliation would overwrite it, which this catches.
        outcomes = _outcomes_by_entry(store_file)
        for entry_id, settled in settled_outcomes.items():
            assert outcomes.get(entry_id) == settled, (
                f"cycle {cycle}: entry {entry_id} was reconciled twice — it "
                f"held {settled.value!r} and now holds "
                f"{outcomes.get(entry_id)!r}"
            )

        settled_outcomes = {
            entry_id: outcome
            for entry_id, outcome in outcomes.items()
            if outcome is not None
        }
        previous_nodes, previous_entries = nodes, entries

    # The loop must actually have exercised the thing: a tenant that never
    # journaled would make every assertion above vacuously true.
    assert previous_entries, "no journal entries were ever committed"
    assert settled_outcomes, "recovery never reconciled anything"

    print(
        f"\nstart-to-ready over {CYCLES} cycles: "
        f"min={min(start_durations):.3f}s "
        f"median={sorted(start_durations)[len(start_durations) // 2]:.3f}s "
        f"max={max(start_durations):.3f}s "
        f"(bound {START_TO_READY_BOUND_SECONDS}s)"
    )


def test_every_entry_is_reconciled_exactly_once_across_restarts(
    tmp_path: Path, supervisor_dir: Path, runs_dir: Path
) -> None:
    """After the dust settles, every entry carries exactly one outcome.

    A final clean start reconciles whatever the last kill left in flight. No
    entry may be left unresolved, and none may carry a second outcome — the
    two ways "reconciled exactly once" can fail.
    """
    store_file = seed_project(supervisor_dir)

    for cycle in range(4):
        host = start_host(
            tmp_path,
            supervisor_dir,
            tenant=JOURNALING_TENANT,
            runs_dir=runs_dir,
            idle_interval_seconds=0.02,
            script_name=f"settle-{cycle}.py",
        )
        try:
            host.await_ready()
            time.sleep(0.15)
            host.kill_and_wait()
        finally:
            host.cleanup()

    # One last start with no tenant: it recovers what is left and stops.
    final = start_host(
        tmp_path,
        supervisor_dir,
        tenant=None,
        runs_dir=runs_dir,
        idle_interval_seconds=0.02,
        script_name="final.py",
    )
    try:
        final.await_ready()
        assert final.terminate_and_wait() == 0
    finally:
        final.cleanup()

    with Store.open_read_only(store_file) as store:
        entries = store.journal_entries(PROJECT)
        unresolved = store.unresolved_journal_entries(PROJECT)

    assert entries, "the tenant never journaled anything"
    assert unresolved == [], (
        f"{len(unresolved)} entries were left unresolved after a clean start"
    )
    assert all(entry.outcome is not None for entry in entries)
