"""The tick budget refuses a call at the deadline or after a stop request."""

from __future__ import annotations

from amoeba.runner.budget import TickBudget, TickResult


class FakeHost:
    def __init__(self) -> None:
        self.stop_requested = False


class FakeClock:
    def __init__(self, now: float) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


def test_a_call_is_allowed_before_the_deadline() -> None:
    clock = FakeClock(10.0)

    assert TickBudget(15.0, FakeHost(), clock).allows_call()


def test_a_call_is_refused_at_and_after_the_deadline() -> None:
    clock = FakeClock(10.0)
    budget = TickBudget(15.0, FakeHost(), clock)

    clock.now = 15.0
    assert not budget.allows_call()
    clock.now = 99.0
    assert not budget.allows_call()


def test_a_stop_request_refuses_a_call_before_the_deadline() -> None:
    host = FakeHost()
    budget = TickBudget(15.0, host, FakeClock(10.0))
    assert budget.allows_call()

    host.stop_requested = True

    assert not budget.allows_call()


def test_the_results_are_distinct() -> None:
    assert TickResult.COMPLETE != TickResult.CUT_OFF
