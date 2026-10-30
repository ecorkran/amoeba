"""D3: a step's dispatch state, every row of the table and the edges between them."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace

import pytest

from amoeba.runner.dispatch.state import DispatchState, dispatch_state
from amoeba.runner.supervise import RESULT_OUTCOME_DOCUMENT
from amoeba.store import (
    PARAM_RESOLUTION,
    BlockedKind,
    BlockedState,
    CommandKind,
    JournalEntry,
    JournalOutcome,
    JournalResolver,
    Resolution,
    ResolutionOutcome,
)

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


def _run_stopped_at(document: Mapping[str, object]) -> JournalEntry:
    """A resolved run entry holding the outcome document it was resolved with."""
    entry = _run()
    return replace(entry, result={RESULT_OUTCOME_DOCUMENT: document})


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
    assert (
        dispatch_state([], None, pointer_confirmed=True) is DispatchState.NEEDS_POINTER
    )


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
    assert (
        dispatch_state(entries, None, pointer_confirmed=True) is DispatchState.IN_FLIGHT
    )


def test_a_run_recovery_found_never_started_is_reissued() -> None:
    entries = [
        _pointer(),
        _run(JournalOutcome.NOT_APPLIED, resolved_by=JournalResolver.RECOVERY),
    ]

    assert (
        dispatch_state(entries, None, pointer_confirmed=False) is DispatchState.REISSUE
    )


@pytest.mark.parametrize("outcome", [JournalOutcome.COMPLETED, JournalOutcome.ADOPTED])
def test_a_landed_pointer_write_confirmed_now_is_pointed(
    outcome: JournalOutcome,
) -> None:
    assert (
        dispatch_state([_pointer(outcome)], None, pointer_confirmed=True)
        is DispatchState.POINTED
    )


@pytest.mark.parametrize("outcome", [JournalOutcome.COMPLETED, JournalOutcome.ADOPTED])
def test_a_landed_pointer_write_not_confirmed_now_needs_a_pointer(
    outcome: JournalOutcome,
) -> None:
    assert (
        dispatch_state([_pointer(outcome)], None, pointer_confirmed=False)
        is DispatchState.NEEDS_POINTER
    )


def test_a_failed_pointer_write_needs_a_pointer() -> None:
    entries = [_pointer(JournalOutcome.FAILED)]

    assert (
        dispatch_state(entries, None, pointer_confirmed=True)
        is DispatchState.NEEDS_POINTER
    )


def test_a_routed_run_needs_a_pointer_again() -> None:
    """The decision cleared the flag; the next attempt starts with the pointer."""
    entries = [_pointer(), _run(awaits_routing=False)]

    assert (
        dispatch_state(entries, None, pointer_confirmed=True)
        is DispatchState.NEEDS_POINTER
    )


@pytest.mark.parametrize("outcome", [JournalOutcome.UNKNOWN, JournalOutcome.ADOPTED])
def test_a_run_recovery_resolved_unknown_or_adopted_needs_a_pointer(
    outcome: JournalOutcome,
) -> None:
    entries = [_pointer(), _run(outcome, resolved_by=JournalResolver.RECOVERY)]

    assert (
        dispatch_state(entries, None, pointer_confirmed=True)
        is DispatchState.NEEDS_POINTER
    )


def test_a_pointer_write_after_a_routed_run_is_pointed() -> None:
    entries = [_pointer(), _run(), _pointer()]

    assert (
        dispatch_state(entries, None, pointer_confirmed=True) is DispatchState.POINTED
    )


# -- the latest applied resolution (slice 127, D5) ------------------------------


def _decided(
    decision: str | None,
    outcome: ResolutionOutcome | None = ResolutionOutcome.APPLIED,
) -> BlockedState:
    return BlockedState(
        id="b-1",
        node_id="node-1",
        kind=BlockedKind.HUMAN,
        context="decide",
        resolution=Resolution(resolved_by="pm", detail="go", decision=decision),
        runner_outcome=outcome,
    )


def _naming(entry: JournalEntry, resolution_id: str = "b-1") -> JournalEntry:
    return replace(entry, parameters={PARAM_RESOLUTION: resolution_id})


@pytest.mark.parametrize(
    ("decision", "expected"),
    [
        ("retry", DispatchState.RESUME),
        ("accept", DispatchState.RESUME),
        ("handled", DispatchState.REOBSERVE),
        ("rerun", DispatchState.NEEDS_POINTER),
    ],
)
def test_an_applied_decision_nobody_carried_out_decides(
    decision: str, expected: DispatchState
) -> None:
    entries = [_run(awaits_routing=False)]

    assert (
        dispatch_state(entries, _decided(decision), pointer_confirmed=True) is expected
    )


@pytest.mark.parametrize("decision", ["retry", "accept", "handled", "rerun"])
def test_once_an_entry_names_it_the_older_rules_apply(decision: str) -> None:
    entries = [_run(), _naming(_pointer())]

    state = dispatch_state(entries, _decided(decision), pointer_confirmed=True)

    assert state is DispatchState.POINTED


def test_rerun_after_a_not_applied_entry_is_not_a_reissue() -> None:
    not_applied = _run(JournalOutcome.NOT_APPLIED, resolved_by=JournalResolver.RECOVERY)

    older = dispatch_state([not_applied], None, pointer_confirmed=True)
    rerun = dispatch_state([not_applied], _decided("rerun"), pointer_confirmed=True)

    assert older is DispatchState.REISSUE
    assert rerun is DispatchState.NEEDS_POINTER


@pytest.mark.parametrize(
    "resolution",
    [
        _decided("retry", ResolutionOutcome.REJECTED),
        _decided("retry", None),
        _decided(None),
        _decided("stop"),
        BlockedState(id="b", node_id="n", kind=BlockedKind.HUMAN, context="c"),
        None,
    ],
)
def test_a_rejected_undecided_or_stop_resolution_changes_nothing(
    resolution: BlockedState | None,
) -> None:
    entries = [_run(), _pointer()]

    state = dispatch_state(entries, resolution, pointer_confirmed=True)

    assert state is DispatchState.POINTED


def test_an_unresolved_continuation_is_in_flight() -> None:
    entries = [_run(), _naming(_run(None))]

    state = dispatch_state(entries, _decided("retry"), pointer_confirmed=True)

    assert state is DispatchState.IN_FLIGHT


_RUN_ID = "run-1"
_TRANSIENT_DOCUMENTS: dict[str, dict[str, object]] = {
    "orphaned": {"run_id": _RUN_ID, "outcome": "orphaned"},
    "provider_error": {
        "run_id": _RUN_ID,
        "outcome": "failed",
        "failure": {"kind": "provider_error", "step": "design-0"},
    },
    "stall": {
        "run_id": _RUN_ID,
        "outcome": "failed",
        "failure": {"kind": "stall", "step": "design-0"},
    },
    "usage_limit": {
        "run_id": _RUN_ID,
        "outcome": "paused",
        "checkpoint": {
            "kind": "usage_limit",
            "step": "design-0",
            "resets_at": "2026-10-29T18:00:00+00:00",
        },
    },
}


@pytest.mark.parametrize("name", list(_TRANSIENT_DOCUMENTS))
def test_a_transient_outcome_gives_auto_resume(name: str) -> None:
    document = _TRANSIENT_DOCUMENTS[name]
    entries = [_pointer(), _run_stopped_at(document)]

    state = dispatch_state(entries, None, pointer_confirmed=True)

    assert state is DispatchState.AUTO_RESUME


@pytest.mark.parametrize(
    "document",
    [
        {"run_id": _RUN_ID, "outcome": "completed"},
        {
            "run_id": _RUN_ID,
            "outcome": "failed",
            "failure": {"kind": "cost_cap", "step": "design-0"},
        },
        {
            "run_id": _RUN_ID,
            "outcome": "paused",
            "checkpoint": {"kind": "usage_limit", "step": "design-0"},
        },
        {
            "run_id": _RUN_ID,
            "outcome": "paused",
            "checkpoint": {"kind": "agent_question", "step": "design-0"},
        },
    ],
    ids=["completed", "cost_cap", "usage_limit_without_resets_at", "agent_question"],
)
def test_an_outcome_that_is_not_transient_is_not_resumed(
    document: Mapping[str, object],
) -> None:
    entries = [_pointer(), _run_stopped_at(document)]

    state = dispatch_state(entries, None, pointer_confirmed=True)

    assert state is not DispatchState.AUTO_RESUME


def test_a_run_with_no_recorded_document_is_not_resumed() -> None:
    state = dispatch_state([_pointer(), _run()], None, pointer_confirmed=True)

    assert state is DispatchState.NEEDS_POINTER


def test_a_pointer_written_after_the_transient_run_starts_over() -> None:
    document = _TRANSIENT_DOCUMENTS["stall"]
    entries = [_run_stopped_at(document), _pointer()]

    state = dispatch_state(entries, None, pointer_confirmed=True)

    assert state is DispatchState.POINTED


def test_an_unresolved_transient_resume_is_in_flight() -> None:
    entries = [_run_stopped_at(_TRANSIENT_DOCUMENTS["stall"]), _run(None)]

    state = dispatch_state(entries, None, pointer_confirmed=True)

    assert state is DispatchState.IN_FLIGHT
