"""D4: which checkouts are held, across the whole project."""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from pathlib import Path

import pytest

from amoeba.runner.dispatch.checkout import CheckoutUnresolved
from amoeba.runner.dispatch.facts import StepDispatchFacts
from amoeba.runner.dispatch.hold import checkout_holders
from amoeba.runner.dispatch.state import DispatchState
from amoeba.store import CommandKind, JournalEntry, JournalOutcome, JournalResolver
from runner.dispatch.dispatch_support import FIRST, SECOND, entry, facts

RUN = CommandKind.SQ_RUN
POINTER = CommandKind.CF_WRITE


def _held(
    entries: Sequence[JournalEntry],
    done: Collection[str],
    current: Mapping[str, StepDispatchFacts],
) -> frozenset[Path]:
    return frozenset(checkout_holders(entries, done, current))


def test_nothing_is_held_without_entries_or_current_steps() -> None:
    assert _held([], set(), {}) == frozenset()


def test_an_unresolved_run_holds_its_checkout() -> None:
    assert _held([entry(RUN, "a")], set(), {}) == {FIRST}


def test_an_unresolved_run_holds_even_when_its_step_is_not_current() -> None:
    held = _held(
        [entry(RUN, "excluded")],
        set(),
        {"other": facts(DispatchState.NEEDS_POINTER, SECOND)},
    )

    assert held == {FIRST}


def test_a_paused_run_of_a_node_that_is_not_done_holds_its_checkout() -> None:
    paused = entry(RUN, "a", outcome=JournalOutcome.COMPLETED, outcome_text="paused")

    assert _held([paused], set(), {}) == {FIRST}


def test_a_paused_run_of_a_done_node_holds_nothing() -> None:
    paused = entry(RUN, "a", outcome=JournalOutcome.COMPLETED, outcome_text="paused")

    assert _held([paused], {"a"}, {}) == frozenset()


def test_a_later_run_on_the_node_releases_a_paused_one() -> None:
    paused = entry(RUN, "a", outcome=JournalOutcome.COMPLETED, outcome_text="paused")
    resumed = entry(
        RUN, "a", outcome=JournalOutcome.COMPLETED, outcome_text="completed"
    )

    assert _held([paused, resumed], set(), {}) == frozenset()


def test_the_recorded_outcome_decides_not_the_block() -> None:
    """A paused run whose review was unknown is blocked on a human, and still holds."""
    paused = entry(RUN, "a", outcome=JournalOutcome.COMPLETED, outcome_text="paused")
    completed = entry(
        RUN,
        "b",
        outcome=JournalOutcome.COMPLETED,
        outcome_text="completed",
        checkout=SECOND,
    )

    assert _held([paused, completed], set(), {}) == {FIRST}


@pytest.mark.parametrize("outcome_text", ["failed", "orphaned"])
def test_a_failed_or_orphaned_run_of_a_node_that_is_not_done_holds_its_checkout(
    outcome_text: str,
) -> None:
    stopped = entry(
        RUN, "a", outcome=JournalOutcome.COMPLETED, outcome_text=outcome_text
    )

    assert _held([stopped], set(), {}) == {FIRST}
    assert _held([stopped], {"a"}, {}) == frozenset()


def test_a_recovery_resolved_run_holds_nothing() -> None:
    adopted = entry(
        RUN,
        "a",
        outcome=JournalOutcome.NOT_APPLIED,
        resolved_by=JournalResolver.RECOVERY,
    )

    assert _held([adopted], set(), {}) == frozenset()


def test_a_pointed_current_step_holds_its_checkout() -> None:
    held = _held([], set(), {"a": facts(DispatchState.POINTED, SECOND)})

    assert held == {SECOND}


def test_a_pointer_write_in_flight_holds_while_its_step_is_current() -> None:
    pointer = entry(POINTER, "a")
    current = {"a": facts(DispatchState.IN_FLIGHT)}

    assert _held([pointer], set(), current) == {FIRST}


def test_a_pointer_claim_lapses_when_its_step_stops_being_current() -> None:
    pointer = entry(POINTER, "a")

    assert _held([pointer], set(), {}) == frozenset()


def test_a_step_that_needs_a_pointer_holds_nothing_yet() -> None:
    current = {"a": facts(DispatchState.NEEDS_POINTER)}

    assert _held([], set(), current) == frozenset()


def test_an_unresolved_checkout_holds_nothing() -> None:
    current = {"a": facts(DispatchState.POINTED, CheckoutUnresolved("no snapshot"))}

    assert _held([], set(), current) == frozenset()


def test_an_entry_without_a_checkout_holds_nothing() -> None:
    assert _held([entry(RUN, "a", checkout=None)], set(), {}) == frozenset()


def test_different_checkouts_are_held_independently() -> None:
    entries = [entry(RUN, "a", checkout=FIRST), entry(RUN, "b", checkout=SECOND)]

    assert _held(entries, set(), {}) == {FIRST, SECOND}


def test_holders_name_every_node_behind_a_held_checkout() -> None:
    pointed = facts(DispatchState.POINTED, FIRST)

    holders = checkout_holders([entry(RUN, "a")], set(), {"b": pointed})

    assert holders == {FIRST: {"a", "b"}}


def test_a_paused_run_is_held_by_its_own_node_only() -> None:
    paused = entry(RUN, "a", outcome=JournalOutcome.COMPLETED, outcome_text="paused")

    assert checkout_holders([paused], set(), {}) == {FIRST: {"a"}}
