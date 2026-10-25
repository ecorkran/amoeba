"""D2's outcome bullets: what each pointer-write result writes to the store."""

from __future__ import annotations

import dataclasses
from collections.abc import Iterator
from pathlib import Path

import pytest
from cf_stub import (
    GET_MODE_ENV,
    GET_QUIRK_ENV,
    SET_MODE_ENV,
    GetQuirk,
    PointerMode,
    write_cf_state,
)

from amoeba.process import (
    RESULT_FILE_SLICE,
    RESULT_PROJECT_PATH,
    RESULT_UPDATED_AT,
    RESULT_WORKTREE_ID,
)
from amoeba.runner.dispatch.pointer import (
    PointerAttempt,
    SetCutOff,
    SetFailed,
    issue_pointer_write,
    read_back,
)
from amoeba.runner.dispatch.pointer_apply import apply_answer, apply_attempt
from amoeba.runner.faults import PAYLOAD_FAULT_KIND, FaultKind
from amoeba.runner.ingest.outcome import PAYLOAD_REASON
from amoeba.runner.launch import STDERR_TAIL_LIMIT_BYTES
from amoeba.store import (
    BlockedKind,
    Channel,
    JournalEntry,
    JournalOutcome,
    JournalResolver,
    NodeKind,
    Store,
)
from runner.dispatch.pointer_support import (
    CF_ID,
    PROJECT,
    STEM,
    TIMEOUT,
    Rig,
    generous_budget,
)


@pytest.fixture
def rig(tmp_path: Path, store: Store) -> Iterator[Rig]:
    yield Rig(tmp_path, store)


def _attempt(rig: Rig, knobs: dict[str, str] | None = None) -> PointerAttempt:
    attempt = issue_pointer_write(
        rig.store, rig.action(), rig.run(knobs), TIMEOUT, generous_budget()
    )
    assert attempt is not None
    return attempt


def _entry(rig: Rig, attempt: PointerAttempt) -> JournalEntry:
    entry = rig.store.journal_entry(attempt.entry.id)
    assert entry is not None
    return entry


def _open_blocks(rig: Rig) -> list[BlockedKind]:
    states = rig.store.all_blocked_states(rig.node.id)
    return [state.kind for state in states if not state.is_resolved]


def _payloads(rig: Rig) -> list[dict[str, object]]:
    messages = rig.store.messages(PROJECT, channel=Channel.ESCALATION)
    return [dict(message.payload or {}) for message in messages]


def test_a_confirmed_pointer_resolves_completed_and_names_the_slice(rig: Rig) -> None:
    attempt = _attempt(rig)

    apply_attempt(rig.store, attempt)

    done = _entry(rig, attempt)
    assert done.outcome is JournalOutcome.COMPLETED
    assert done.resolved_by is JournalResolver.ISSUER
    assert done.awaits_routing is False, "a pointer write is not routed"
    assert done.result is not None
    assert set(done.result) == {
        RESULT_UPDATED_AT,
        RESULT_FILE_SLICE,
        RESULT_WORKTREE_ID,
        RESULT_PROJECT_PATH,
    }
    assert done.result[RESULT_FILE_SLICE] == STEM
    assert done.result[RESULT_WORKTREE_ID] == "wt_a"
    slice_node = rig.store.get_node(rig.slice_node.id)
    assert slice_node is not None
    assert slice_node.cf.slice_name == "run-dispatch-and-outcome-ingestion"
    assert slice_node.cf.index == 125, "the rest of the reference is kept"
    assert _open_blocks(rig) == []


def test_applying_a_confirmation_to_a_named_slice_changes_no_reference(
    rig: Rig,
) -> None:
    first = _attempt(rig)
    apply_attempt(rig.store, first)
    before = rig.store.get_node(rig.slice_node.id)

    second = _attempt(rig)
    apply_attempt(rig.store, second)

    assert rig.store.get_node(rig.slice_node.id) == before


def test_another_index_blocks_the_step_and_resolves_failed(rig: Rig) -> None:
    write_cf_state(
        rig.state_path,
        cf_project_id=CF_ID,
        project_path=rig.root,
        worktrees=[Rig.worktree_entry("wt_a", rig.root, 100, 199)],
        slices={125: "126-slice.the-wrong-one"},
    )
    attempt = _attempt(rig)

    apply_attempt(rig.store, attempt)

    assert _entry(rig, attempt).outcome is JournalOutcome.FAILED
    assert _open_blocks(rig) == [BlockedKind.HUMAN]
    [payload] = _payloads(rig)
    assert payload[PAYLOAD_FAULT_KIND] == FaultKind.POINTER_WRITE_FAILED.value


@pytest.mark.parametrize(
    "quirk", [GetQuirk.OTHER_PROJECT_PATH, GetQuirk.OTHER_WORKTREE_ID]
)
def test_a_path_or_worktree_mismatch_blocks_and_resolves_failed(
    rig: Rig, quirk: GetQuirk
) -> None:
    attempt = _attempt(rig, {GET_QUIRK_ENV: quirk.value})

    apply_attempt(rig.store, attempt)

    assert _entry(rig, attempt).outcome is JournalOutcome.FAILED
    assert _open_blocks(rig) == [BlockedKind.HUMAN]
    assert rig.store.get_node(rig.slice_node.id).cf.slice_name is None  # type: ignore[union-attr]  # pyright: ignore[reportOptionalMemberAccess]


def test_an_answer_that_cannot_be_judged_is_escalated_at_once(rig: Rig) -> None:
    attempt = _attempt(rig, {GET_QUIRK_ENV: GetQuirk.OMIT_FILE_SLICE.value})

    apply_attempt(rig.store, attempt)

    escalated = _entry(rig, attempt)
    assert escalated.outcome is JournalOutcome.UNKNOWN
    assert escalated.resolved_by is JournalResolver.RECOVERY
    assert _open_blocks(rig) == [BlockedKind.HUMAN]


def test_a_read_that_failed_leaves_the_entry_open(rig: Rig) -> None:
    attempt = _attempt(rig, {GET_MODE_ENV: PointerMode.FAIL.value})

    apply_attempt(rig.store, attempt)

    assert not _entry(rig, attempt).is_resolved
    assert _open_blocks(rig) == []


def test_a_failed_set_blocks_with_the_bounded_head_and_resolves_failed(
    rig: Rig,
) -> None:
    attempt = _attempt(rig, {SET_MODE_ENV: PointerMode.FAIL.value})

    apply_attempt(rig.store, attempt)

    assert _entry(rig, attempt).outcome is JournalOutcome.FAILED
    [payload] = _payloads(rig)
    assert "cf set exited 1" in str(payload[PAYLOAD_REASON])
    assert len(str(payload[PAYLOAD_REASON]).encode()) <= STDERR_TAIL_LIMIT_BYTES


def test_an_oversized_set_failure_is_cut_to_the_bound(rig: Rig) -> None:
    attempt = _attempt(rig, {SET_MODE_ENV: PointerMode.FAIL.value})
    huge = SetFailed(1, "x" * (STDERR_TAIL_LIMIT_BYTES * 3))

    apply_attempt(rig.store, PointerAttempt(attempt.entry, huge, None))

    [payload] = _payloads(rig)
    assert len(str(payload[PAYLOAD_REASON]).encode()) <= STDERR_TAIL_LIMIT_BYTES


def test_a_set_that_was_cut_off_writes_nothing(rig: Rig) -> None:
    attempt = _attempt(rig)
    cut = PointerAttempt(attempt.entry, SetCutOff("timed out"), None)

    apply_attempt(rig.store, cut)

    assert not _entry(rig, attempt).is_resolved
    assert _open_blocks(rig) == []


def test_a_later_read_back_finishes_the_entry_the_same_way(rig: Rig) -> None:
    """A cut-off between the write and its read-back: the next tick's read-back."""
    attempt = _attempt(rig)
    pending = PointerAttempt(attempt.entry, attempt.set_result, None)
    apply_attempt(rig.store, pending)
    assert not _entry(rig, attempt).is_resolved

    answer = read_back(attempt.entry, rig.action().checkout, rig.run(), TIMEOUT)
    apply_answer(rig.store, attempt.entry, answer)

    assert _entry(rig, attempt).outcome is JournalOutcome.COMPLETED


def test_a_step_with_no_slice_node_blocks_instead_of_raising(rig: Rig) -> None:
    orphan = rig.store.create_node(
        project_id=PROJECT, kind=NodeKind.PHASE_OR_ARTIFACT, title="orphan"
    )
    action = dataclasses.replace(rig.action(), node_id=orphan.id)
    attempt = issue_pointer_write(
        rig.store, action, rig.run(), TIMEOUT, generous_budget()
    )
    assert attempt is not None

    apply_attempt(rig.store, attempt)

    assert _entry(rig, attempt).outcome is JournalOutcome.FAILED
    [blocked] = rig.store.all_blocked_states(orphan.id)
    assert blocked.kind is BlockedKind.HUMAN
