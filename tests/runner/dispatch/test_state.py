"""D3: a step's dispatch state, every row of the table and the edges between them."""

from __future__ import annotations

import pytest

from amoeba.runner.dispatch.state import DispatchState, dispatch_state
from amoeba.store import CommandKind, JournalEntry, JournalOutcome, JournalResolver

_COUNTER = [0]


def _entry(
    kind: CommandKind,
    outcome: JournalOutcome | None = None,
    *,
    resolved_by: JournalResolver | None = None,
    awaits_routing: bool = False,
) -> JournalEntry:
    _COUNTER[0] += 1
    return JournalEntry(
        id=f"entry-{_COUNTER[0]}",
        project_id="demo",
        node_id="node-1",
        kind=kind,
        outcome=outcome,
        resolved_by=(
            resolved_by
            if resolved_by is not None or outcome is None
            else JournalResolver.ISSUER
        ),
        awaits_routing=awaits_routing,
    )


def _pointer(outcome: JournalOutcome | None = JournalOutcome.COMPLETED) -> JournalEntry:
    resolver = (
        JournalResolver.RECOVERY
        if outcome in {JournalOutcome.ADOPTED, JournalOutcome.NOT_APPLIED}
        else None
    )
    return _entry(CommandKind.CF_WRITE, outcome, resolved_by=resolver)


def _run(
    outcome: JournalOutcome | None = JournalOutcome.COMPLETED,
    *,
    resolved_by: JournalResolver | None = None,
    awaits_routing: bool = False,
) -> JournalEntry:
    return _entry(
        CommandKind.SQ_RUN,
        outcome,
        resolved_by=resolved_by,
        awaits_routing=awaits_routing,
    )


def test_no_entries_needs_a_pointer() -> None:
    assert dispatch_state([], pointer_confirmed=True) is DispatchState.NEEDS_POINTER


@pytest.mark.parametrize(
    "entries",
    [
        [_pointer(None)],
        [_run(None)],
        [_pointer(), _run(None)],
        [_run(awaits_routing=True), _pointer(None)],
    ],
    ids=["open pointer", "open run", "pointed then open run", "open pointer after run"],
)
def test_any_unresolved_entry_is_in_flight(entries: list[JournalEntry]) -> None:
    assert dispatch_state(entries, pointer_confirmed=True) is DispatchState.IN_FLIGHT


def test_a_resolved_run_with_the_flag_awaits_routing() -> None:
    entries = [_pointer(), _run(awaits_routing=True)]

    assert (
        dispatch_state(entries, pointer_confirmed=True)
        is DispatchState.AWAITING_ROUTING
    )


def test_a_failed_run_with_the_flag_awaits_routing_too() -> None:
    entries = [_pointer(), _run(JournalOutcome.FAILED, awaits_routing=True)]

    assert (
        dispatch_state(entries, pointer_confirmed=False)
        is DispatchState.AWAITING_ROUTING
    )


def test_a_run_recovery_found_never_started_is_reissued() -> None:
    entries = [
        _pointer(),
        _run(JournalOutcome.NOT_APPLIED, resolved_by=JournalResolver.RECOVERY),
    ]

    assert dispatch_state(entries, pointer_confirmed=False) is DispatchState.REISSUE


@pytest.mark.parametrize("outcome", [JournalOutcome.COMPLETED, JournalOutcome.ADOPTED])
def test_a_landed_pointer_write_confirmed_now_is_pointed(
    outcome: JournalOutcome,
) -> None:
    assert (
        dispatch_state([_pointer(outcome)], pointer_confirmed=True)
        is DispatchState.POINTED
    )


@pytest.mark.parametrize("outcome", [JournalOutcome.COMPLETED, JournalOutcome.ADOPTED])
def test_a_landed_pointer_write_not_confirmed_now_needs_a_pointer(
    outcome: JournalOutcome,
) -> None:
    assert (
        dispatch_state([_pointer(outcome)], pointer_confirmed=False)
        is DispatchState.NEEDS_POINTER
    )


def test_a_failed_pointer_write_needs_a_pointer() -> None:
    entries = [_pointer(JournalOutcome.FAILED)]

    assert (
        dispatch_state(entries, pointer_confirmed=True) is DispatchState.NEEDS_POINTER
    )


def test_a_routed_run_needs_a_pointer_again() -> None:
    """The decision cleared the flag; the next attempt starts with the pointer."""
    entries = [_pointer(), _run(awaits_routing=False)]

    assert (
        dispatch_state(entries, pointer_confirmed=True) is DispatchState.NEEDS_POINTER
    )


@pytest.mark.parametrize("outcome", [JournalOutcome.UNKNOWN, JournalOutcome.ADOPTED])
def test_a_run_recovery_resolved_unknown_or_adopted_needs_a_pointer(
    outcome: JournalOutcome,
) -> None:
    entries = [_pointer(), _run(outcome, resolved_by=JournalResolver.RECOVERY)]

    assert (
        dispatch_state(entries, pointer_confirmed=True) is DispatchState.NEEDS_POINTER
    )


def test_a_pointer_write_after_a_routed_run_is_pointed() -> None:
    entries = [_pointer(), _run(), _pointer()]

    assert dispatch_state(entries, pointer_confirmed=True) is DispatchState.POINTED
