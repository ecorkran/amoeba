"""The door version and the shared times are pinned together (slice 260, D7)."""

from __future__ import annotations

from amoeba.store.store import BUSY_TIMEOUT_SECONDS
from amoeba.wire import times


def test_a_kept_result_outlives_the_longest_call() -> None:
    assert times.CALL_RESULT_LIFETIME_SECONDS > times.CALL_BOUND_SECONDS


def test_the_call_bound_is_worked_out_not_written() -> None:
    assert times.CALL_BOUND_SECONDS == (
        times.RETRY_SECONDS + times.CONNECT_SECONDS + times.READ_SECONDS
    )


def test_the_version_and_the_times_equal_a_pinned_tuple() -> None:
    """Changing a time must change the version, so this tuple changes with it."""
    assert (
        times.DOOR_VERSION,
        times.CONNECT_SECONDS,
        times.READ_SECONDS,
        times.RETRY_SECONDS,
        times.RETRY_PAUSE_SECONDS,
        times.CALL_BOUND_SECONDS,
        times.CALL_RESULT_LIFETIME_SECONDS,
    ) == (2, 3, 10, 30, 0.5, 43, 600)


def test_door_times_default_to_the_constants() -> None:
    door_times = times.DoorTimes()

    assert door_times.connect_seconds == times.CONNECT_SECONDS
    assert door_times.read_seconds == times.READ_SECONDS
    assert door_times.retry_seconds == times.RETRY_SECONDS
    assert door_times.retry_pause_seconds == times.RETRY_PAUSE_SECONDS


def test_a_read_outlasts_the_one_store_lock_wait_a_call_makes() -> None:
    assert times.READ_SECONDS > BUSY_TIMEOUT_SECONDS
