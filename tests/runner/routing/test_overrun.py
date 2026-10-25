"""A run past its time bound raises one escalation, and is never killed (D7).

The run is held open by the stub ``sq``'s "still going" answer. Journal entries are
stamped with the real clock while the rig's clock starts in the past, so the test
moves the rig's clock to the real instant before it measures any age.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sq_stub_scripts import single_review

from amoeba.process import RunOutcome
from amoeba.runner.dispatch.pointer_watch import PAYLOAD_RUNS
from amoeba.runner.faults import FaultKind
from amoeba.runner.launch import log_paths
from amoeba.store import (
    PARAM_RUN_ID,
    CommandKind,
    JournalEntry,
    Message,
    Node,
    Store,
)
from runner.dispatch.tick_rig import DispatchRig
from runner.observe_support import NOW, document
from runner.routing.table_support import small_table

PROJECT = "demo"
SLICE = "overrun"
INDEX = 125
CF_SLUG = "run-dispatch-and-outcome-ingestion"
ONE_MINUTE = {"P4": 1, "P5": 1, "P6": 1}
ADVANCE_PASS = """\
- id: advance-on-pass
  when: {outcome: completed, verdict: pass}
  route: advance
"""
BEYOND_THE_BOUND_SECONDS = 120.0
WITHIN_THE_BOUND_SECONDS = 30.0
POLL_GAP_SECONDS = 20.0


@pytest.fixture
def rig(tmp_path: Path, store: Store) -> Iterator[DispatchRig]:
    rig = DispatchRig(tmp_path, store)
    rig.tick_rig.routing_table = small_table(ADVANCE_PASS, bounds=ONE_MINUTE)
    yield rig


def _run_in_flight(rig: DispatchRig) -> tuple[Node, JournalEntry]:
    """A launched, confirmed run; the rig's clock stands at the real instant."""
    node = rig.step(SLICE, INDEX)
    rig.tick()
    rig.tick()
    entry = rig.run_of(node)
    run_id = str(entry.parameters[PARAM_RUN_ID])
    rig.tick_rig.tracker.confirm(entry.id)
    log_paths(rig.tick_rig.supervisor_dir, entry.id).stderr.write_text(
        f"run_id={run_id}\n"
    )
    rig.tick_rig.clock.seconds = (datetime.now(UTC) - NOW).total_seconds()
    return node, entry


def _still_going(rig: DispatchRig, entry: JournalEntry, seconds: float) -> None:
    """Move the clock on, answer the next poll with "still running", and tick."""
    run_id = str(entry.parameters[PARAM_RUN_ID])
    rig.tick_rig.poll.answers.append(document(run_id, RunOutcome.TIMED_OUT))
    rig.tick_rig.clock.seconds += seconds
    rig.tick()


def _open_overruns(rig: DispatchRig) -> list[Message]:
    return [
        m
        for m in rig.store.open_project_escalations(PROJECT)
        if m.fault_kind == FaultKind.RUN_OVERRUN.value
    ]


def test_a_run_within_its_bound_raises_nothing(rig: DispatchRig) -> None:
    _, entry = _run_in_flight(rig)

    _still_going(rig, entry, WITHIN_THE_BOUND_SECONDS)

    assert _open_overruns(rig) == []


def test_a_run_past_its_bound_raises_one_escalation_naming_it(
    rig: DispatchRig,
) -> None:
    node, entry = _run_in_flight(rig)

    _still_going(rig, entry, BEYOND_THE_BOUND_SECONDS)

    [escalation] = _open_overruns(rig)
    payload = dict(escalation.payload or {})
    [listed] = payload[PAYLOAD_RUNS]  # type: ignore[misc]
    assert listed["node_id"] == node.id  # pyright: ignore[reportUnknownMemberType]
    assert listed["run_id"] == entry.parameters[PARAM_RUN_ID]  # pyright: ignore[reportUnknownMemberType]
    assert listed["pipeline"] == "P4"  # pyright: ignore[reportUnknownMemberType]
    assert listed["bound_minutes"] == 1  # pyright: ignore[reportUnknownMemberType]
    assert payload["table_version"] == rig.tick_rig.routing_table.version


def test_the_run_is_not_killed_and_is_still_polled(rig: DispatchRig) -> None:
    _, entry = _run_in_flight(rig)
    run_id = str(entry.parameters[PARAM_RUN_ID])

    _still_going(rig, entry, BEYOND_THE_BOUND_SECONDS)
    asked = len(rig.tick_rig.poll.asked)
    _still_going(rig, entry, POLL_GAP_SECONDS)

    assert len(rig.tick_rig.poll.asked) == asked + 1, "polled again"
    assert set(rig.tick_rig.poll.asked) == {run_id}
    still = rig.store.journal_entry(entry.id)
    assert still is not None and not still.is_resolved


def test_a_second_tick_while_overrun_adds_no_second_escalation(
    rig: DispatchRig,
) -> None:
    _, entry = _run_in_flight(rig)

    _still_going(rig, entry, BEYOND_THE_BOUND_SECONDS)
    _still_going(rig, entry, POLL_GAP_SECONDS)

    assert len(_open_overruns(rig)) == 1


def test_the_escalation_closes_when_the_run_is_ingested_and_routed(
    rig: DispatchRig,
) -> None:
    node, entry = _run_in_flight(rig)
    _still_going(rig, entry, BEYOND_THE_BOUND_SECONDS)
    assert len(_open_overruns(rig)) == 1

    review = single_review(CF_SLUG)
    passing = {
        path: text.replace("verdict: CONCERNS", "verdict: PASS", 1)
        for path, text in review.files.items()
    }
    for relative, text in passing.items():
        target = rig.world.root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    rig.end_run(node, RunOutcome.COMPLETED, **review.document)

    resolved = rig.store.journal_entry(entry.id)
    assert resolved is not None and resolved.is_resolved
    assert rig.store.routing_decision_for_entry(entry.id) is not None, "routed"
    assert _open_overruns(rig) == [], "closed on the first complete tick after"
    assert len(rig.entries(CommandKind.SQ_RUN, node)) == 1
