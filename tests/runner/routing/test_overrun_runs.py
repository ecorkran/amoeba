"""``overrun_runs`` and ``watch_overruns``: pure, table-driven (D7)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest
from sq_run_fixtures import sq_run_parameters

from amoeba.runner.dispatch.pointer_watch import PAYLOAD_RUNS
from amoeba.runner.faults import FaultKind, TickFaults
from amoeba.runner.routing.overrun import (
    LISTING_BOUND_MINUTES,
    overrun_runs,
    watch_overruns,
)
from amoeba.store import CommandKind, JournalEntry
from runner.routing.table_support import small_table

NOW = datetime(2026, 10, 25, 12, 0, tzinfo=UTC)
TABLE = small_table(bounds={"P4": 10, "P5": 20, "P6": 30})


def _entry(
    entry_id: str,
    pipeline: str | None,
    age_minutes: float | None,
    *,
    issued_at: datetime | None = None,
) -> JournalEntry:
    parameters: dict[str, object] = sq_run_parameters(
        {"params": {}}, run_id=f"run-{entry_id}"
    )
    if pipeline is not None:
        parameters["pipeline"] = pipeline
    when = issued_at
    if when is None and age_minutes is not None:
        when = NOW - timedelta(minutes=age_minutes)
    return JournalEntry(
        id=entry_id,
        project_id="demo",
        node_id=f"node-{entry_id}",
        kind=CommandKind.SQ_RUN,
        parameters=parameters,
        issued_at=when,
    )


@pytest.mark.parametrize(
    ("age_minutes", "overran"),
    [(9.9, False), (10.0, False), (10.01, True), (500.0, True), (0.0, False)],
)
def test_a_run_overruns_only_past_its_bound(age_minutes: float, overran: bool) -> None:
    found = overrun_runs([_entry("a", "P4", age_minutes)], TABLE, NOW)
    assert bool(found) is overran


def test_each_pipeline_is_held_to_its_own_bound() -> None:
    entries = [_entry("a", "P4", 15), _entry("b", "P5", 15), _entry("c", "P6", 15)]
    found = overrun_runs(entries, TABLE, NOW)
    assert [o.pipeline for o in found] == ["P4"]
    assert found[0].bound_minutes == 10


def test_several_runs_with_one_over_lists_only_that_one() -> None:
    entries = [_entry("a", "P4", 1), _entry("b", "P4", 11), _entry("c", "P5", 2)]
    [only] = overrun_runs(entries, TABLE, NOW)
    assert (only.node_id, only.run_id) == ("node-b", "run-b")
    assert only.issued_at == NOW - timedelta(minutes=11)


def test_nothing_in_flight_overruns_nothing() -> None:
    assert overrun_runs([], TABLE, NOW) == ()


def test_an_unbounded_pipeline_is_a_programming_error() -> None:
    with pytest.raises(ValueError, match="no time bound"):
        overrun_runs([_entry("a", "P9", 1)], TABLE, NOW)


def test_an_entry_without_a_pipeline_is_a_programming_error() -> None:
    with pytest.raises(ValueError, match="no pipeline"):
        overrun_runs([_entry("a", None, 1)], TABLE, NOW)


def test_a_missing_issued_at_is_a_programming_error() -> None:
    with pytest.raises(ValueError, match="issued_at"):
        overrun_runs([_entry("a", "P4", None)], TABLE, NOW)


def test_a_naive_issued_at_is_a_programming_error() -> None:
    entry = _entry("a", "P4", None, issued_at=datetime(2026, 10, 25, 11, 0))
    with pytest.raises(ValueError, match="timezone-aware"):
        overrun_runs([entry], TABLE, NOW)


def test_a_non_utc_issued_at_is_compared_as_an_instant() -> None:
    plus_two = timezone(timedelta(hours=2))
    issued = datetime(2026, 10, 25, 14, 0, tzinfo=plus_two) - timedelta(minutes=11)
    assert overrun_runs([_entry("a", "P4", None, issued_at=issued)], TABLE, NOW)


def test_watching_adds_one_fault_naming_every_overrun_and_the_table() -> None:
    faults = TickFaults()
    entries = [_entry("a", "P4", 11), _entry("b", "P5", 25), _entry("c", "P6", 1)]

    watch_overruns(entries, TABLE, NOW, faults)

    [fault] = list(faults)
    assert fault.kind is FaultKind.RUN_OVERRUN
    assert fault.extra is not None
    assert fault.extra["table_version"] == TABLE.version
    runs = fault.extra[PAYLOAD_RUNS]
    assert isinstance(runs, list)
    assert [run[LISTING_BOUND_MINUTES] for run in runs] == [10, 20]  # pyright: ignore[reportUnknownVariableType]


def test_watching_adds_nothing_when_no_run_overran() -> None:
    faults = TickFaults()
    watch_overruns([_entry("a", "P4", 1)], TABLE, NOW, faults)
    assert len(faults) == 0
