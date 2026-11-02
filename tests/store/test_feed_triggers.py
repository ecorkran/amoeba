"""Emission triggers: every write to a tracked table emits its change, once."""

from __future__ import annotations

import sqlite3

import pytest
from evidence_harness import (
    REVIEW_TYPE,
    check_input,
    progress_input,
    provider_failure,
    verdict_input,
)
from feed_harness import (
    apply,
    escalate_by_recovery,
    post_intent,
    raw_changes,
    resolve_by_submission,
)
from legacy_nodes import LEGACY_INSERT_NODE
from question_harness import catch_for, submit_resolution

from amoeba.store import (
    BlockedKind,
    BlockEffect,
    CFReference,
    Channel,
    DeclineReason,
    NodeKind,
    NodeStatus,
    QuestionState,
    ResolutionOutcome,
    Store,
    SubmissionKind,
    SubmissionOutcome,
)
from amoeba.store.feed_models import (
    SILENT_OUTCOMES,
    ChangeKind,
    DetectionInput,
    DetectionOutcome,
)

PROJECT = "demo"


def _node(store: Store, status: NodeStatus = NodeStatus.RUNNABLE) -> str:
    return store.create_node(
        project_id=PROJECT, kind=NodeKind.SLICE, title="n", status=status
    ).id


def _of_kind(store: Store, kind: ChangeKind) -> list[dict[str, object]]:
    return [dict(c.payload) for c in raw_changes(store, PROJECT) if c.kind is kind]


# --------------------------------------------------------------------------
# Nodes
# --------------------------------------------------------------------------


def test_create_node_emits_one_node_created_with_the_initial_status(
    store: Store,
) -> None:
    parent = _node(store)
    child = store.create_node(
        project_id=PROJECT,
        kind=NodeKind.GATE,
        title="c",
        parent_id=parent,
        status=NodeStatus.IN_PROGRESS,
    )

    changes = raw_changes(store, PROJECT)
    assert [c.kind for c in changes] == [ChangeKind.NODE_CREATED] * 2
    last = changes[-1]
    assert (last.node_id, last.subject_id) == (child.id, child.id)
    assert last.payload == {
        "kind": NodeKind.GATE.value,
        "parent_id": parent,
        "status": NodeStatus.IN_PROGRESS.value,
    }
    assert last.recorded_at == child.created_at


def test_a_status_update_emits_from_and_to(store: Store) -> None:
    node_id = _node(store)
    updated = store.update_node_status(node_id, NodeStatus.DONE)

    changes = raw_changes(store, PROJECT)
    assert changes[-1].kind is ChangeKind.NODE_STATUS_CHANGED
    assert changes[-1].payload == {
        "from": NodeStatus.RUNNABLE.value,
        "to": NodeStatus.DONE.value,
    }
    assert changes[-1].recorded_at == updated.updated_at


def test_an_update_to_the_same_status_emits_nothing(store: Store) -> None:
    node_id = _node(store)
    store.update_node_status(node_id, NodeStatus.RUNNABLE)
    assert _of_kind(store, ChangeKind.NODE_STATUS_CHANGED) == []


def test_block_and_resolve_each_emit_their_transition(store: Store) -> None:
    node_id = _node(store)
    store.block(node_id, kind=BlockedKind.HUMAN, context="decide")
    store.resolve(node_id, resolved_by="pm", detail="go")

    assert _of_kind(store, ChangeKind.NODE_STATUS_CHANGED) == [
        {"from": NodeStatus.RUNNABLE.value, "to": NodeStatus.BLOCKED_ON_HUMAN.value},
        {"from": NodeStatus.BLOCKED_ON_HUMAN.value, "to": NodeStatus.RUNNABLE.value},
    ]


def test_other_node_updates_emit_nothing(store: Store) -> None:
    node_id = _node(store)
    store.update_cf_reference(node_id, CFReference(slice_name="renamed"))
    assert _of_kind(store, ChangeKind.NODE_STATUS_CHANGED) == []


def test_a_rolled_back_write_leaves_no_change(store: Store) -> None:
    with sqlite3.connect(store.path) as connection:
        connection.execute("BEGIN")
        connection.execute(
            LEGACY_INSERT_NODE,
            ("n-x", PROJECT, None, "slice", "runnable", "x")
            + (None,) * 7
            + ("2026-10-15T00:00:00+00:00",) * 2,
        )
        connection.rollback()
    assert raw_changes(store, PROJECT) == []


# --------------------------------------------------------------------------
# Verdicts and messages
# --------------------------------------------------------------------------


def test_record_verdict_emits_one_verdict_recorded(store: Store) -> None:
    node_id = _node(store)
    record = store.record_verdict(verdict_input("v-1", node_id), project_id=PROJECT)

    change = raw_changes(store, PROJECT)[-1]
    assert change.kind is ChangeKind.VERDICT_RECORDED
    assert (change.node_id, change.subject_id) == (node_id, "v-1")
    assert change.recorded_at == record.recorded_at


def test_the_verdict_payload_keys_are_exactly_the_three(store: Store) -> None:
    node_id = _node(store)
    store.record_verdict(verdict_input("v-1", node_id), project_id=PROJECT)
    assert _of_kind(store, ChangeKind.VERDICT_RECORDED) == [
        {"verdict": "CONCERNS", "review_type": REVIEW_TYPE, "provider_failure": False}
    ]


def test_a_retried_record_verdict_emits_nothing(store: Store) -> None:
    node_id = _node(store)
    store.record_verdict(verdict_input("v-1", node_id), project_id=PROJECT)
    store.record_verdict(verdict_input("v-1", node_id), project_id=PROJECT)
    assert len(_of_kind(store, ChangeKind.VERDICT_RECORDED)) == 1


def test_a_provider_failure_is_a_json_true(store: Store) -> None:
    node_id = _node(store)
    store.record_verdict(provider_failure("v-1", node_id), project_id=PROJECT)
    payload = _of_kind(store, ChangeKind.VERDICT_RECORDED)[0]
    assert payload["provider_failure"] is True


# --------------------------------------------------------------------------
# Checks and progress records
# --------------------------------------------------------------------------


def test_record_check_emits_one_check_recorded(store: Store) -> None:
    node_id = _node(store)
    record = store.record_check(check_input("c-1", node_id), project_id=PROJECT)

    change = raw_changes(store, PROJECT)[-1]
    assert change.kind is ChangeKind.CHECK_RECORDED
    assert (change.node_id, change.subject_id) == (node_id, "c-1")
    assert change.recorded_at == record.recorded_at


def test_the_check_payload_keys_are_exactly_the_three_and_carry_no_standing(
    store: Store,
) -> None:
    node_id = _node(store)
    store.record_check(
        check_input("c-1", node_id, examined_count=0), project_id=PROJECT
    )
    store.record_check(
        check_input("c-2", node_id, examined_count=None), project_id=PROJECT
    )
    assert _of_kind(store, ChangeKind.CHECK_RECORDED) == [
        {"name": "cf check", "outcome": "passed", "examined_count": 0},
        {"name": "cf check", "outcome": "passed", "examined_count": None},
    ]


def test_a_retried_check_emits_nothing(store: Store) -> None:
    node_id = _node(store)
    store.record_check(check_input("c-1", node_id), project_id=PROJECT)
    store.record_check(check_input("c-1", node_id), project_id=PROJECT)
    assert len(_of_kind(store, ChangeKind.CHECK_RECORDED)) == 1


def test_a_progress_record_emits_nothing(store: Store) -> None:
    node_id = _node(store)
    before = len(raw_changes(store, PROJECT))
    store.record_progress(progress_input("p-1", node_id), project_id=PROJECT)
    assert len(raw_changes(store, PROJECT)) == before


def test_a_check_rejected_through_the_inbox_emits_nothing(store: Store) -> None:
    node_id = _node(store)
    payload: dict[str, object] = {
        "node_id": node_id,
        "name": "cf check",
        "outcome": "passed",
        "examined_count": -1,
        "upstream": "context-forge",
        "upstream_version": "1.2.3",
        "source": "command_output",
    }
    record = apply(store, "s-1", SubmissionKind.CHECK, payload, PROJECT)
    assert record.outcome is SubmissionOutcome.REJECTED
    assert _of_kind(store, ChangeKind.CHECK_RECORDED) == []


def test_an_intent_submission_emits_one_message_posted(store: Store) -> None:
    node_id = _node(store)
    post_intent(store, "s-1", node_id, PROJECT)

    posted = [
        c for c in raw_changes(store, PROJECT) if c.kind is ChangeKind.MESSAGE_POSTED
    ]
    assert len(posted) == 1
    assert posted[0].node_id == node_id
    assert posted[0].payload == {"channel": Channel.INTENT.value}


def test_a_resolution_submission_flips_the_node_to_runnable(store: Store) -> None:
    node_id = _node(store)
    store.block(node_id, kind=BlockedKind.HUMAN, context="decide")
    resolve_by_submission(store, "s-1", node_id, PROJECT)

    assert _of_kind(store, ChangeKind.NODE_STATUS_CHANGED)[-1] == {
        "from": NodeStatus.BLOCKED_ON_HUMAN.value,
        "to": NodeStatus.RUNNABLE.value,
    }


def test_a_recovery_escalation_emits_one_message_posted(store: Store) -> None:
    node_id = _node(store)
    escalate_by_recovery(store, node_id, PROJECT)

    assert _of_kind(store, ChangeKind.MESSAGE_POSTED) == [
        {"channel": Channel.ESCALATION.value}
    ]


# --------------------------------------------------------------------------
# Detections
# --------------------------------------------------------------------------


def _detect(store: Store, outcome: DetectionOutcome, path: str = "/r/a.md") -> int:
    return store.record_detection(
        DetectionInput(project_id=PROJECT, path=path, digest="d", outcome=outcome)
    ).id


@pytest.mark.parametrize(
    "outcome",
    [o for o in DetectionOutcome if o not in SILENT_OUTCOMES],
)
def test_a_loud_outcome_emits_one_review_detected(
    store: Store, outcome: DetectionOutcome
) -> None:
    ledger_id = _detect(store, outcome)
    (change,) = raw_changes(store, PROJECT)
    assert change.kind is ChangeKind.REVIEW_DETECTED
    assert change.subject_id == str(ledger_id)
    assert change.payload == {"outcome": outcome.value, "path": "/r/a.md"}


@pytest.mark.parametrize("outcome", sorted(SILENT_OUTCOMES))
def test_a_silent_outcome_emits_nothing(
    store: Store, outcome: DetectionOutcome
) -> None:
    _detect(store, outcome)
    assert raw_changes(store, PROJECT) == []


def test_a_repeated_record_detection_emits_nothing(store: Store) -> None:
    _detect(store, DetectionOutcome.UNPARSEABLE)
    _detect(store, DetectionOutcome.UNPARSEABLE)
    assert len(raw_changes(store, PROJECT)) == 1


# --------------------------------------------------------------------------
# Question records (slice 141, D7)
# --------------------------------------------------------------------------


def _asked(store: Store) -> tuple[str, str]:
    """A recorded question: (record id, its block id)."""
    node_id = _node(store)
    record = store.record_question(
        catch_for(store, node_id), block_context="ctx", block_payload=None
    )
    assert record.blocked_state_id is not None
    return record.id, record.blocked_state_id


def _state_changes(store: Store) -> list[dict[str, object]]:
    return _of_kind(store, ChangeKind.QUESTION_STATE_CHANGED)


def test_recording_a_question_emits_question_recorded(store: Store) -> None:
    record_id, _ = _asked(store)

    recorded = [
        c for c in raw_changes(store, PROJECT) if c.kind is ChangeKind.QUESTION_RECORDED
    ]
    assert [c.subject_id for c in recorded] == [record_id]
    assert dict(recorded[0].payload) == {"state": "pending", "decline_reason": None}


def test_a_decline_emits_one_state_change(store: Store) -> None:
    record_id, _ = _asked(store)

    store.decline_question(record_id, reason=DeclineReason.NO_ANSWER_ON_FILE)

    assert _state_changes(store) == [
        {
            "from": "pending",
            "to": "declined",
            "answered_by": None,
            "decline_reason": "no_answer_on_file",
        }
    ]


def test_a_pm_answer_after_a_decline_emits_declined_to_answered(
    store: Store,
) -> None:
    record_id, block_id = _asked(store)
    store.decline_question(record_id, reason=DeclineReason.NO_ANSWER_ON_FILE)

    submit_resolution(store, block_id, "resume", instructions="go")
    store.acknowledge_resolution(block_id, outcome=ResolutionOutcome.APPLIED)

    changes = _state_changes(store)
    assert [(c["from"], c["to"]) for c in changes] == [
        ("pending", "declined"),
        ("declined", "answered"),
    ]
    assert changes[1]["answered_by"] == "pm"


def test_a_re_point_emits_nothing(store: Store) -> None:
    record_id, block_id = _asked(store)
    submit_resolution(store, block_id, "stop")

    store.acknowledge_resolution(
        block_id,
        outcome=ResolutionOutcome.APPLIED,
        effect=BlockEffect("re-blocked", None),
    )

    assert _state_changes(store) == []
    record = store.question(record_id)
    assert record is not None and record.state is QuestionState.PENDING


def test_question_payloads_carry_no_question_or_answer_text(store: Store) -> None:
    record_id, block_id = _asked(store)
    store.decline_question(record_id, reason=DeclineReason.NO_ANSWER_ON_FILE)
    submit_resolution(store, block_id, "resume", instructions="secret words")
    store.acknowledge_resolution(block_id, outcome=ResolutionOutcome.APPLIED)

    for kind in (ChangeKind.QUESTION_RECORDED, ChangeKind.QUESTION_STATE_CHANGED):
        for payload in _of_kind(store, kind):
            assert "question" not in payload and "answer" not in payload
            assert "secret words" not in str(payload)
