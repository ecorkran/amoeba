"""The stage's stranded pass: an ``answering`` question nothing can settle (D9, D10)."""

from __future__ import annotations

from pathlib import Path

from question_harness import submit_resolution

from amoeba.store import (
    DeclineReason,
    JournalOutcome,
    JournalResolver,
    QuestionState,
    Store,
)
from runner.answering.launch_rig import build_stage_rig


def test_an_entry_resolved_not_applied_by_recovery_declines_run_failed(
    store: Store, tmp_path: Path
) -> None:
    rig = build_stage_rig(tmp_path, store)
    entry = rig.start(rig.launch.record)
    store.journal_resolve(
        entry.id,
        outcome=JournalOutcome.NOT_APPLIED,
        resolved_by=JournalResolver.RECOVERY,
    )

    result = rig.run()

    record = store.question(rig.launch.record.id)
    assert result.wrote
    assert record is not None and record.state is QuestionState.DECLINED
    assert record.decline_reason is DeclineReason.ANSWERING_RUN_FAILED
    assert "not_applied" in (record.decline_detail or "")


def test_an_entry_resolved_unknown_declines_run_failed(
    store: Store, tmp_path: Path
) -> None:
    rig = build_stage_rig(tmp_path, store)
    entry = rig.start(rig.launch.record)
    store.journal_resolve(
        entry.id, outcome=JournalOutcome.UNKNOWN, resolved_by=JournalResolver.RECOVERY
    )

    rig.run()

    record = store.question(rig.launch.record.id)
    assert record is not None
    assert record.decline_reason is DeclineReason.ANSWERING_RUN_FAILED


def test_an_entry_the_stage_resolved_leaving_the_record_declines_discarded(
    store: Store, tmp_path: Path
) -> None:
    rig = build_stage_rig(tmp_path, store)
    entry = rig.start(rig.launch.record)
    store.journal_resolve(entry.id, outcome=JournalOutcome.COMPLETED)

    rig.run()

    record = store.question(rig.launch.record.id)
    assert record is not None
    assert record.decline_reason is DeclineReason.ANSWER_DISCARDED


def test_a_block_awaiting_the_runner_is_skipped(store: Store, tmp_path: Path) -> None:
    rig = build_stage_rig(tmp_path, store)
    entry = rig.start(rig.launch.record)
    store.journal_resolve(entry.id, outcome=JournalOutcome.COMPLETED)
    block_id = rig.launch.record.blocked_state_id or ""
    submit_resolution(store, block_id, "resume", instructions="pm says dev")

    result = rig.run()

    record = store.question(rig.launch.record.id)
    assert not result.wrote
    assert record is not None and record.state is QuestionState.ANSWERING


def test_an_unresolved_entry_is_not_stranded(store: Store, tmp_path: Path) -> None:
    rig = build_stage_rig(tmp_path, store)
    rig.start(rig.launch.record)

    rig.run(allowed=0)

    record = store.question(rig.launch.record.id)
    assert record is not None and record.state is QuestionState.ANSWERING
