"""D2, D3: Observe finishes open pointer writes and confirms pointed steps."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Iterator, Mapping
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from cf_stub import (
    GET_MODE_ENV,
    GET_QUIRK_ENV,
    GetQuirk,
    PointerMode,
    read_cf_state,
)

from amoeba.runner.budget import TickResult
from amoeba.runner.dispatch.observe_pointer import PointerStage
from amoeba.runner.dispatch.pointer import issue_pointer_write
from amoeba.runner.dispatch.pointer_apply import apply_attempt
from amoeba.runner.faults import NodeContext
from amoeba.store import (
    PARAM_CHECKOUT,
    BlockedKind,
    CommandKind,
    JournalEntry,
    JournalOutcome,
    JournalResolver,
    Store,
)
from runner.dispatch.pointer_support import (
    CF_ID,
    PROJECT,
    TIMEOUT,
    Rig,
    budget_allowing,
    generous_budget,
)

GRACE = 30.0


@pytest.fixture
def rig(tmp_path: Path, store: Store) -> Iterator[Rig]:
    yield Rig(tmp_path, store)


def _stage(
    rig: Rig, clock: datetime | None = None, knobs: Mapping[str, str] | None = None
) -> PointerStage:
    when = clock or datetime.now().astimezone()
    return PointerStage(rig.run(knobs), TIMEOUT, GRACE, lambda: when)


def _issue_cut_off(rig: Rig) -> JournalEntry:
    """A pointer write whose ``cf set`` ran and whose read-back never did."""
    attempt = issue_pointer_write(
        rig.store, rig.action(), rig.run(), TIMEOUT, budget_allowing(1)
    )
    assert attempt is not None and attempt.answer is None
    return attempt.entry


def _pointed(rig: Rig) -> None:
    """Complete a pointer write for the rig's step, so its journal says pointed."""
    attempt = issue_pointer_write(
        rig.store, rig.action(), rig.run(), TIMEOUT, generous_budget()
    )
    assert attempt is not None
    apply_attempt(rig.store, attempt)


def _observe(rig: Rig, stage: PointerStage, *, drives: bool = True, budget: Any = None):  # noqa: ANN202
    return stage.observe(
        rig.store,
        PROJECT,
        [rig.node],
        drives=drives,
        budget=budget or generous_budget(),
        context=NodeContext(),
    )


def _entry(rig: Rig, entry: JournalEntry) -> JournalEntry:
    found = rig.store.journal_entry(entry.id)
    assert found is not None
    return found


def test_a_read_back_cut_off_last_tick_completes_on_the_next(rig: Rig) -> None:
    entry = _issue_cut_off(rig)
    assert not _entry(rig, entry).is_resolved

    seen = _observe(rig, _stage(rig))

    assert seen.wrote and seen.result is TickResult.COMPLETE
    assert _entry(rig, entry).outcome is JournalOutcome.COMPLETED


def test_a_record_with_a_field_absent_escalates_at_once(rig: Rig) -> None:
    entry = _issue_cut_off(rig)
    stage = _stage(rig, knobs={GET_QUIRK_ENV: GetQuirk.OMIT_FILE_SLICE.value})

    _observe(rig, stage)

    escalated = _entry(rig, entry)
    assert escalated.outcome is JournalOutcome.UNKNOWN
    assert escalated.resolved_by is JournalResolver.RECOVERY


def test_a_read_that_keeps_failing_escalates_only_after_the_grace(rig: Rig) -> None:
    entry = _issue_cut_off(rig)
    assert entry.issued_at is not None
    failing = {GET_MODE_ENV: PointerMode.FAIL.value}

    early = entry.issued_at + timedelta(seconds=GRACE - 1)
    seen = _observe(rig, _stage(rig, early, failing))
    assert not seen.wrote and not _entry(rig, entry).is_resolved

    late = entry.issued_at + timedelta(seconds=GRACE + 1)
    seen = _observe(rig, _stage(rig, late, failing))
    escalated = _entry(rig, entry)
    assert seen.wrote and escalated.outcome is JournalOutcome.UNKNOWN
    assert [s.kind for s in rig.store.all_blocked_states(rig.node.id)] == [
        BlockedKind.HUMAN
    ]


def test_a_pointed_step_is_confirmed_while_cf_still_points_at_it(rig: Rig) -> None:
    _pointed(rig)

    seen = _observe(rig, _stage(rig))

    assert seen.confirmed == {rig.node.id}


def test_a_pointed_step_whose_pointer_was_overwritten_is_not_confirmed(
    rig: Rig,
) -> None:
    _pointed(rig)
    state = read_cf_state(rig.state_path)
    state["worktrees"][0]["activeSlice"] = "130-slice.someone-else"
    rig.state_path.write_text(json.dumps(state), encoding="utf-8")

    seen = _observe(rig, _stage(rig))

    assert seen.confirmed == frozenset()


def test_a_read_that_fails_does_not_confirm_a_pointed_step(rig: Rig) -> None:
    _pointed(rig)

    seen = _observe(rig, _stage(rig, knobs={GET_MODE_ENV: PointerMode.FAIL.value}))

    assert seen.confirmed == frozenset()


def test_pointed_steps_are_not_read_for_a_project_nobody_drives(rig: Rig) -> None:
    _pointed(rig)
    calls: list[list[str]] = []
    real = rig.run()

    def counting(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        return real(argv, **kwargs)

    stage = PointerStage(counting, TIMEOUT, GRACE, datetime.now().astimezone)

    seen = _observe(rig, stage, drives=False)

    assert seen.confirmed == frozenset() and calls == []


def test_a_budget_that_refuses_a_read_back_cuts_the_stage_off(rig: Rig) -> None:
    entry = _issue_cut_off(rig)

    seen = _observe(rig, _stage(rig), budget=budget_allowing(0))

    assert seen.result is TickResult.CUT_OFF
    assert not _entry(rig, entry).is_resolved


def test_a_cf_write_that_is_not_a_runner_pointer_write_is_left_alone(rig: Rig) -> None:
    other = rig.store.journal_issue(
        rig.node.id,
        kind=CommandKind.CF_WRITE,
        parameters={
            "project": CF_ID,
            "expected": {"developmentPhase": "6"},
            PARAM_CHECKOUT: str(rig.root),
        },
    )

    seen = _observe(rig, _stage(rig))

    assert not seen.wrote
    assert not _entry(rig, other).is_resolved


def test_a_latest_write_that_is_not_a_pointer_write_is_never_confirmed(
    rig: Rig,
) -> None:
    other = rig.store.journal_issue(
        rig.node.id,
        kind=CommandKind.CF_WRITE,
        parameters={"project": CF_ID, "expected": {}, PARAM_CHECKOUT: str(rig.root)},
    )
    rig.store.journal_resolve(other.id, outcome=JournalOutcome.COMPLETED)

    seen = _observe(rig, _stage(rig))

    assert seen.confirmed == frozenset()
