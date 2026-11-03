"""Settling a finished answering run and resolving its entry (slice 144, D9)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from answerer_settings import answerer_settings
from question_harness import PROJECT, catch_for, make_slice, submit_resolution
from sq_stub_scripts import (
    answering_run,
    check_reply,
    declining_answer_reply,
    proposed_answer_reply,
)

from amoeba.process import RunOutcomeDocument
from amoeba.runner.answering.finish import (
    ANSWERER_DETAIL,
    DECISION_CONFIRMED,
    RESULT_DECISION,
    RESULT_QUESTION_OUTCOME,
    RESULT_RUN_OUTCOME,
    QuestionOutcome,
    finish_answering,
    settle_run_result,
)
from amoeba.runner.faults import LaunchFailure
from amoeba.runner.observed import Finished, LaunchFailed, RunEnded
from amoeba.runner.project_config import AnswererSettings
from amoeba.store import (
    AnsweredBy,
    AnsweringLaunch,
    DeclineReason,
    JournalEntry,
    JournalOutcome,
    PassageRef,
    QuestionRecord,
    QuestionState,
    ResolutionOutcome,
    Store,
)

RUN_ID = "run-20261103-finish-0001"
PASSAGES = (
    PassageRef("P1", "docs/rules.md", None, datetime(2026, 11, 1, tzinfo=UTC)),
    PassageRef("P2", "q-7", "q-7", datetime(2026, 10, 30, tzinfo=UTC)),
)
SETTINGS = answerer_settings()
COMPLETED = RunEnded(
    RunOutcomeDocument.model_validate({"run_id": RUN_ID, "outcome": "completed"})
)


def _begin(store: Store, scratch: Path) -> tuple[QuestionRecord, JournalEntry]:
    """A pending question moved to ``answering`` with its entry journaled."""
    node_id = make_slice(store)
    pending = store.record_question(
        catch_for(store, node_id, question="which branch?"),
        block_context="ctx",
        block_payload=None,
    )
    scratch.mkdir(parents=True, exist_ok=True)
    launch = AnsweringLaunch(
        node_id=node_id,
        run_id=RUN_ID,
        parameters={
            "run_id": RUN_ID,
            "pipeline": "answering.yaml",
            "params": {},
            "scratch": str(scratch),
        },
        source_commit="abc123",
        passages=PASSAGES,
        dropped_pm_answers=(),
    )
    begun = store.begin_answering(pending.id, launch)
    assert begun.entry is not None and begun.record is not None
    return begun.record, begun.entry


def _write_replies(
    scratch: Path,
    answer: dict[str, object] | str | None,
    check: dict[str, object] | str | None,
) -> None:
    for name, content in answering_run(answer, check).files.items():
        (scratch / name).write_text(content, encoding="utf-8")


def _confirming(scratch: Path) -> None:
    _write_replies(
        scratch,
        proposed_answer_reply("use main", ["P1"]),
        check_reply("yes", "matches P1"),
    )


def _reload(store: Store, record: QuestionRecord) -> QuestionRecord:
    found = store.question(record.id)
    assert found is not None
    return found


def _entry(store: Store, entry: JournalEntry) -> JournalEntry:
    found = store.journal_entry(entry.id)
    assert found is not None
    return found


def _settle(
    store: Store,
    record: QuestionRecord,
    entry: JournalEntry,
    finished: Finished = COMPLETED,
    settings: AnswererSettings = SETTINGS,
) -> QuestionOutcome:
    return settle_run_result(store, record, entry, finished, settings).question_outcome


def test_a_confirmed_answer_is_submitted_by_the_answerer(
    store: Store, tmp_path: Path
) -> None:
    record, entry = _begin(store, tmp_path / "s")
    _confirming(tmp_path / "s")

    outcome = _settle(store, record, entry)

    answered = _reload(store, record)
    assert outcome is QuestionOutcome.SUBMITTED
    assert answered.state is QuestionState.ANSWERED
    assert answered.answered_by is AnsweredBy.ANSWERER
    assert answered.answer == "use main"
    assert answered.cited_passages == ("P1",)
    assert answered.check_verdict == "yes"
    assert answered.proposed_answer == "use main"
    block = store.blocked_state(record.blocked_state_id or "")
    assert block is not None and block.resolution is not None
    assert block.resolution.instructions == "You asked: which branch?\nAnswer: use main"
    assert block.resolution.detail == ANSWERER_DETAIL


def test_a_gate_refusal_declines_with_the_gates_reason_and_keeps_the_evidence(
    store: Store, tmp_path: Path
) -> None:
    record, entry = _begin(store, tmp_path / "s")
    _confirming(tmp_path / "s")

    outcome = _settle(
        store, record, entry, settings=answerer_settings(reserved_terms=("main",))
    )

    declined = _reload(store, record)
    assert outcome is QuestionOutcome.DECLINED
    assert declined.state is QuestionState.DECLINED
    assert declined.decline_reason is DeclineReason.RESERVED_TERM
    assert declined.reserved_term == "main"
    assert declined.proposed_answer == "use main"
    assert declined.cited_passages == ("P1",)


def test_a_check_saying_no_declines_with_reason_detail_and_evidence(
    store: Store, tmp_path: Path
) -> None:
    record, entry = _begin(store, tmp_path / "s")
    _write_replies(
        tmp_path / "s",
        proposed_answer_reply("use main", ["P1"]),
        check_reply("no", "P1 says dev"),
    )

    outcome = _settle(store, record, entry)

    declined = _reload(store, record)
    assert outcome is QuestionOutcome.DECLINED
    assert declined.decline_reason is DeclineReason.CHECK_SAID_NO
    assert declined.decline_detail == "P1 says dev"
    assert declined.check_verdict == "no"
    assert declined.proposed_answer == "use main"


def test_an_unfinished_launch_declines_without_reading_any_file(
    store: Store, tmp_path: Path
) -> None:
    record, entry = _begin(store, tmp_path / "s")
    failed = LaunchFailed(LaunchFailure.SPAWN_ERROR, None, "no such file: sq")

    outcome = _settle(store, record, entry, failed)

    declined = _reload(store, record)
    assert outcome is QuestionOutcome.DECLINED
    assert declined.decline_reason is DeclineReason.ANSWERING_LAUNCH_FAILED
    assert declined.decline_detail == "no such file: sq"


def test_a_pm_answer_first_discards_the_run_and_leaves_the_record(
    store: Store, tmp_path: Path
) -> None:
    record, entry = _begin(store, tmp_path / "s")
    _confirming(tmp_path / "s")
    block_id = record.blocked_state_id or ""
    submit_resolution(store, block_id, "resume", instructions="pm says dev")
    store.acknowledge_resolution(block_id, outcome=ResolutionOutcome.APPLIED)
    answered_by_pm = _reload(store, record)
    assert answered_by_pm.answered_by is AnsweredBy.PM

    outcome = _settle(store, answered_by_pm, entry)

    assert outcome is QuestionOutcome.DISCARDED
    assert _reload(store, record) == answered_by_pm


def test_a_resolved_block_not_yet_acknowledged_writes_nothing(
    store: Store, tmp_path: Path
) -> None:
    record, entry = _begin(store, tmp_path / "s")
    _confirming(tmp_path / "s")
    submit_resolution(store, record.blocked_state_id or "", "resume", instructions="x")

    outcome = _settle(store, record, entry)

    assert outcome is QuestionOutcome.BLOCK_RESOLVED
    assert _reload(store, record) == record


def test_a_record_settled_after_it_was_read_writes_nothing(
    store: Store, tmp_path: Path
) -> None:
    stale, entry = _begin(store, tmp_path / "s")
    _confirming(tmp_path / "s")
    block_id = stale.blocked_state_id or ""
    submit_resolution(store, block_id, "resume", instructions="pm says dev")
    store.acknowledge_resolution(block_id, outcome=ResolutionOutcome.APPLIED)
    answered_by_pm = _reload(store, stale)

    # ``stale`` is the record as read before the PM's answer was acknowledged.
    outcome = _settle(store, stale, entry)

    assert outcome is QuestionOutcome.SETTLED
    assert _reload(store, stale) == answered_by_pm


def test_a_record_linked_to_another_entry_is_discarded(
    store: Store, tmp_path: Path
) -> None:
    record, entry = _begin(store, tmp_path / "s")
    _, other_entry = _begin(store, tmp_path / "other")

    assert _settle(store, record, other_entry) is QuestionOutcome.DISCARDED
    assert _reload(store, record) == record
    assert entry.id != other_entry.id


# --------------------------------------------------------------------------
# finish_answering: the entry
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("replies", "expected", "decision"),
    [
        (
            (proposed_answer_reply("use main", ["P1"]), check_reply("yes", "ok")),
            QuestionOutcome.SUBMITTED,
            DECISION_CONFIRMED,
        ),
        (
            (declining_answer_reply("no basis"), None),
            QuestionOutcome.DECLINED,
            DeclineReason.ANSWERER_DECLINED.value,
        ),
    ],
)
def test_the_entry_is_resolved_with_the_outcome_and_decision(
    store: Store,
    tmp_path: Path,
    replies: tuple[dict[str, object], dict[str, object] | None],
    expected: QuestionOutcome,
    decision: str,
) -> None:
    record, entry = _begin(store, tmp_path / "s")
    _write_replies(tmp_path / "s", *replies)

    finish_answering(store, entry, COMPLETED, SETTINGS)

    resolved = _entry(store, entry)
    assert resolved.outcome is JournalOutcome.COMPLETED
    assert resolved.result is not None
    assert resolved.result[RESULT_QUESTION_OUTCOME] == expected.value
    assert resolved.result[RESULT_DECISION] == decision
    assert resolved.result[RESULT_RUN_OUTCOME] == "completed"
    assert resolved.result["run_id"] == RUN_ID
    assert not resolved.awaits_routing
    assert _reload(store, record).state is not QuestionState.ANSWERING


def test_a_run_that_did_not_complete_resolves_the_entry_as_failed(
    store: Store, tmp_path: Path
) -> None:
    _, entry = _begin(store, tmp_path / "s")
    failed = LaunchFailed(LaunchFailure.EXITED_BEFORE_LINE, 1, "boom")

    finish_answering(store, entry, failed, SETTINGS)

    resolved = _entry(store, entry)
    assert resolved.outcome is JournalOutcome.FAILED
    assert resolved.result is not None
    assert resolved.result[RESULT_RUN_OUTCOME] == "launch_failed"
    assert resolved.result[RESULT_DECISION] == DeclineReason.ANSWERING_LAUNCH_FAILED


def test_a_pm_answer_first_is_a_discarded_result(store: Store, tmp_path: Path) -> None:
    record, entry = _begin(store, tmp_path / "s")
    _confirming(tmp_path / "s")
    block_id = record.blocked_state_id or ""
    submit_resolution(store, block_id, "resume", instructions="pm")
    store.acknowledge_resolution(block_id, outcome=ResolutionOutcome.APPLIED)

    finish_answering(store, entry, COMPLETED, SETTINGS)

    resolved = _entry(store, entry)
    assert resolved.result is not None
    assert resolved.result[RESULT_QUESTION_OUTCOME] == QuestionOutcome.DISCARDED.value
    assert _reload(store, record).answered_by is AnsweredBy.PM


def test_finishing_again_after_a_crash_before_the_resolve_changes_nothing(
    store: Store, tmp_path: Path
) -> None:
    record, entry = _begin(store, tmp_path / "s")
    _confirming(tmp_path / "s")
    _settle(store, record, entry)  # the record is settled; the entry is not
    settled = _reload(store, record)
    submissions = store.submissions(PROJECT)

    finish_answering(store, entry, COMPLETED, SETTINGS)

    assert _reload(store, record) == settled
    assert store.submissions(PROJECT) == submissions
    resolved = _entry(store, entry)
    assert resolved.is_resolved and resolved.result is not None
    assert resolved.result[RESULT_QUESTION_OUTCOME] == QuestionOutcome.SUBMITTED.value
    assert json.dumps(resolved.result)  # the result is plain JSON


def test_finishing_again_after_a_declined_crash_does_not_decline_twice(
    store: Store, tmp_path: Path
) -> None:
    record, entry = _begin(store, tmp_path / "s")
    _write_replies(tmp_path / "s", declining_answer_reply("no basis"), None)
    _settle(store, record, entry)
    declined = _reload(store, record)

    finish_answering(store, entry, COMPLETED, SETTINGS)

    assert _reload(store, record) == declined
    resolved = _entry(store, entry)
    assert resolved.result is not None
    assert resolved.result[RESULT_QUESTION_OUTCOME] == QuestionOutcome.DECLINED.value
