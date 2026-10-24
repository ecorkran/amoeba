"""Plan read cadence: interval, snapshot trigger, cut-off, failure state."""

from __future__ import annotations

from datetime import UTC, datetime

from amoeba.runner.lifecycle.cadence import LinkSnapshots, PlanReadSchedule
from amoeba.store import CFSnapshot, CFSnapshotOutcome

INTERVAL = 30.0
PROJECT = "demo"
LINK = "cf-1"
OTHER_LINK = "cf-2"
OBSERVED_AT = datetime(2026, 10, 23, 12, 0, tzinfo=UTC)

NO_SNAPSHOTS: LinkSnapshots = (None, None)
CHANGE: list[dict[str, object]] = [{"field": "activeSlice"}]


class Clock:
    def __init__(self) -> None:
        self.seconds = 0.0

    def __call__(self) -> float:
        return self.seconds


def _snapshot(
    snapshot_id: int,
    *,
    changed: list[dict[str, object]] | None,
    outcome: CFSnapshotOutcome = CFSnapshotOutcome.OBSERVED,
) -> CFSnapshot:
    observed = outcome is CFSnapshotOutcome.OBSERVED
    return CFSnapshot(
        id=snapshot_id,
        project_id=PROJECT,
        cf_project_id=LINK,
        outcome=outcome,
        state={} if observed else None,
        changed=changed if observed else None,
        detail=None if observed else "unreadable",
        cf_updated_at=None,
        cf_version_label="test",
        observed_at=OBSERVED_AT,
    )


def _observed(snapshot: CFSnapshot) -> LinkSnapshots:
    return (snapshot, snapshot)


def _schedule() -> tuple[PlanReadSchedule, Clock]:
    clock = Clock()
    return PlanReadSchedule(INTERVAL, clock), clock


def _read_completes(schedule: PlanReadSchedule) -> None:
    schedule.record_complete(PROJECT, LINK)


def test_a_link_is_due_on_first_sight() -> None:
    schedule, _ = _schedule()

    assert schedule.due(PROJECT, LINK, NO_SNAPSHOTS)


def test_a_link_is_not_due_before_the_interval_and_due_at_it() -> None:
    schedule, clock = _schedule()
    schedule.due(PROJECT, LINK, NO_SNAPSHOTS)
    _read_completes(schedule)

    clock.seconds = INTERVAL - 0.1
    assert not schedule.due(PROJECT, LINK, NO_SNAPSHOTS)
    clock.seconds = INTERVAL
    assert schedule.due(PROJECT, LINK, NO_SNAPSHOTS)


def test_the_interval_restarts_from_each_complete_read() -> None:
    schedule, clock = _schedule()
    schedule.due(PROJECT, LINK, NO_SNAPSHOTS)
    _read_completes(schedule)
    clock.seconds = 100.0
    _read_completes(schedule)

    clock.seconds = 100.0 + INTERVAL - 0.1
    assert not schedule.due(PROJECT, LINK, NO_SNAPSHOTS)


def test_a_changed_snapshot_makes_the_link_due_now() -> None:
    schedule, _ = _schedule()
    schedule.due(PROJECT, LINK, NO_SNAPSHOTS)
    _read_completes(schedule)
    assert not schedule.due(PROJECT, LINK, NO_SNAPSHOTS)

    assert schedule.due(PROJECT, LINK, _observed(_snapshot(1, changed=CHANGE)))


def test_the_same_snapshot_id_twice_is_not_a_second_trigger() -> None:
    schedule, _ = _schedule()
    changed = _observed(_snapshot(1, changed=CHANGE))
    schedule.due(PROJECT, LINK, changed)
    _read_completes(schedule)

    assert not schedule.due(PROJECT, LINK, changed)


def test_a_newer_changed_snapshot_triggers_again() -> None:
    schedule, _ = _schedule()
    schedule.due(PROJECT, LINK, _observed(_snapshot(1, changed=CHANGE)))
    _read_completes(schedule)

    assert schedule.due(PROJECT, LINK, _observed(_snapshot(2, changed=CHANGE)))


def test_a_failed_snapshot_makes_no_early_read() -> None:
    schedule, _ = _schedule()
    schedule.due(PROJECT, LINK, NO_SNAPSHOTS)
    _read_completes(schedule)
    failed = _snapshot(5, changed=None, outcome=CFSnapshotOutcome.UNREADABLE)

    # The latest row is the failure; the latest observed row is unchanged (none).
    assert not schedule.due(PROJECT, LINK, (failed, None))


def test_a_recovery_with_no_change_is_seen_and_triggers_nothing() -> None:
    schedule, _ = _schedule()
    schedule.due(PROJECT, LINK, NO_SNAPSHOTS)
    _read_completes(schedule)

    recovery = _observed(_snapshot(7, changed=[]))
    assert not schedule.due(PROJECT, LINK, recovery)
    assert not schedule.due(PROJECT, LINK, recovery)


def test_a_cut_off_read_stays_due_on_the_next_call() -> None:
    schedule, _ = _schedule()
    snapshots = _observed(_snapshot(1, changed=CHANGE))
    assert schedule.due(PROJECT, LINK, snapshots)

    schedule.record_cut_off(PROJECT, LINK)

    assert schedule.due(PROJECT, LINK, snapshots), "the trigger is not consumed"


def test_a_cut_off_first_read_stays_due() -> None:
    schedule, _ = _schedule()
    schedule.due(PROJECT, LINK, NO_SNAPSHOTS)

    schedule.record_cut_off(PROJECT, LINK)

    assert schedule.due(PROJECT, LINK, NO_SNAPSHOTS)


def test_last_failed_is_set_by_a_failure_and_cleared_by_a_complete_read() -> None:
    schedule, _ = _schedule()
    assert not schedule.last_failed(PROJECT, LINK)

    schedule.due(PROJECT, LINK, NO_SNAPSHOTS)
    schedule.record_failed(PROJECT, LINK)
    assert schedule.last_failed(PROJECT, LINK)
    assert schedule.due(PROJECT, LINK, NO_SNAPSHOTS), "a failed link is retried"

    _read_completes(schedule)
    assert not schedule.last_failed(PROJECT, LINK)


def test_a_cut_off_does_not_clear_a_failure() -> None:
    schedule, _ = _schedule()
    schedule.due(PROJECT, LINK, NO_SNAPSHOTS)
    schedule.record_failed(PROJECT, LINK)

    schedule.record_cut_off(PROJECT, LINK)

    assert schedule.last_failed(PROJECT, LINK)


def test_two_links_are_independent() -> None:
    schedule, clock = _schedule()
    schedule.due(PROJECT, LINK, NO_SNAPSHOTS)
    _read_completes(schedule)
    schedule.record_failed(PROJECT, OTHER_LINK)

    clock.seconds = 1.0
    assert not schedule.due(PROJECT, LINK, NO_SNAPSHOTS)
    assert schedule.due(PROJECT, OTHER_LINK, NO_SNAPSHOTS)
    assert not schedule.last_failed(PROJECT, LINK)
    assert schedule.last_failed(PROJECT, OTHER_LINK)


def test_the_same_link_in_two_projects_is_independent() -> None:
    schedule, _ = _schedule()
    schedule.due(PROJECT, LINK, NO_SNAPSHOTS)
    _read_completes(schedule)

    assert schedule.due("other-project", LINK, NO_SNAPSHOTS)
