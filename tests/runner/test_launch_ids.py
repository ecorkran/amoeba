"""Minted run ids match Squadron's rule and do not collide."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

from amoeba.runner.faults import STORE_FAILURES, FaultKind, LaunchFailure
from amoeba.runner.launch import SQUADRON_RUN_ID_PATTERN, mint_run_id

NOW = datetime(2026, 10, 23, 10, 15, 0, tzinfo=UTC)


def test_a_fixed_now_gives_the_prefix_and_thirty_six_characters() -> None:
    run_id = mint_run_id(NOW)

    assert run_id.startswith("amoeba-20261023T101500Z-")
    assert len(run_id) == 36


def test_many_mints_match_the_pattern_and_are_unique() -> None:
    ids = [mint_run_id(NOW) for _ in range(2000)]

    assert all(SQUADRON_RUN_ID_PATTERN.fullmatch(run_id) for run_id in ids)
    assert len(set(ids)) == len(ids)


def test_a_non_utc_now_is_converted_to_utc() -> None:
    offset = timezone(timedelta(hours=5, minutes=30))

    run_id = mint_run_id(NOW.astimezone(offset))

    assert run_id.startswith("amoeba-20261023T101500Z-")


def test_the_pattern_refuses_what_squadron_refuses() -> None:
    assert not SQUADRON_RUN_ID_PATTERN.fullmatch("-leading")
    assert not SQUADRON_RUN_ID_PATTERN.fullmatch("has space")
    assert not SQUADRON_RUN_ID_PATTERN.fullmatch("a" * 129)
    assert SQUADRON_RUN_ID_PATTERN.fullmatch("a" * 128)


def test_the_fault_vocabulary_values_are_stable() -> None:
    assert {kind.value for kind in FaultKind} == {
        "run_observation_failed",
        "launch_overdue",
        "cf_probe_failed",
        "unexpected_fault",
        "plan_read_failed",
        "lifecycle_orphan",
        "plan_status_unknown",
    }
    assert {failure.value for failure in LaunchFailure} == {
        "spawn_error",
        "exited_before_line",
        "usage_error",
    }
    assert all(issubclass(failure, Exception) for failure in STORE_FAILURES)
