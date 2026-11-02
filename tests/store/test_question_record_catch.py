"""``record_question``: block and record in one transaction (slice 141, D1)."""

from __future__ import annotations

from dataclasses import replace

import pytest
from fault_injection import InjectedFailureError, fail_on_statement
from question_harness import PROJECT, catch_for, make_slice

from amoeba.store import (
    BlockedKind,
    Channel,
    DeclineReason,
    InvalidTransitionError,
    NodeNotFoundError,
    NodeStatus,
    QuestionCatch,
    QuestionRecord,
    QuestionState,
    Store,
    sql_questions,
)
from amoeba.store.journal_models import JournalOutcome

CONTEXT = "agent_question: which branch?"
PAYLOAD = {"question": "which branch?", "run_id": "run-test"}


def _record(store: Store, catch: QuestionCatch) -> QuestionRecord:
    return store.record_question(catch, block_context=CONTEXT, block_payload=PAYLOAD)


def test_an_unblocked_node_gets_one_human_block_and_a_pending_record(
    store: Store,
) -> None:
    node_id = make_slice(store)
    catch = catch_for(store, node_id, truncated=True)

    record = _record(store, catch)

    blocked = store.blocked_state_for(node_id)
    assert blocked is not None
    assert blocked.kind is BlockedKind.HUMAN
    assert blocked.context == CONTEXT
    assert record.state is QuestionState.PENDING
    assert record.blocked_state_id == blocked.id
    assert (record.project_id, record.node_id) == (PROJECT, node_id)
    assert (record.source_entry_id, record.run_id) == (
        catch.source_entry_id,
        "run-test",
    )
    assert (record.step, record.question, record.truncated) == (
        "implement",
        "which branch?",
        True,
    )
    assert store.question_for_block(blocked.id) == record
    messages = store.messages(PROJECT, channel=Channel.ESCALATION)
    assert [m.payload for m in messages] == [PAYLOAD]


def test_an_already_blocked_node_gets_a_declined_record_and_no_second_block(
    store: Store,
) -> None:
    node_id = make_slice(store)
    first = store.block(node_id, kind=BlockedKind.HUMAN, context="other")

    record = _record(store, catch_for(store, node_id))

    assert record.state is QuestionState.DECLINED
    assert record.decline_reason is DeclineReason.NODE_ALREADY_BLOCKED
    assert record.blocked_state_id is None
    assert [b.id for b in store.all_blocked_states(node_id)] == [first.id]
    # Only the first block's own escalation: the record wrote no second one.
    assert len(store.messages(PROJECT, channel=Channel.ESCALATION)) == 1


def test_a_retry_returns_the_record_and_writes_nothing_even_after_resolution(
    store: Store,
) -> None:
    node_id = make_slice(store)
    catch = catch_for(store, node_id)
    first = _record(store, catch)
    store.resolve(node_id, resolved_by="pm", detail="go")

    again = _record(store, catch)

    assert again == first
    assert len(store.questions(PROJECT)) == 1
    assert len(list(store.all_blocked_states(node_id))) == 1


def test_a_missing_node_raises_and_writes_nothing(store: Store) -> None:
    node_id = make_slice(store)
    catch = catch_for(store, node_id)
    missing = replace(catch, node_id="no-such-node")

    with pytest.raises(NodeNotFoundError):
        _record(store, missing)

    assert store.questions(PROJECT) == []


def test_a_done_node_raises_and_writes_nothing(store: Store) -> None:
    node_id = make_slice(store)
    catch = catch_for(store, node_id)
    store.journal_resolve(catch.source_entry_id, outcome=JournalOutcome.COMPLETED)
    store.update_node_status(node_id, NodeStatus.DONE)

    with pytest.raises(InvalidTransitionError):
        _record(store, catch)

    assert store.questions(PROJECT) == []
    assert store.blocked_state_for(node_id, include_resolved=True) is None


def test_a_failure_inside_the_transaction_leaves_neither_block_nor_record(
    store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    node_id = make_slice(store)
    catch = catch_for(store, node_id)
    fail_on_statement(monkeypatch, store, sql_questions.INSERT_QUESTION)

    with pytest.raises(InjectedFailureError):
        _record(store, catch)

    monkeypatch.undo()
    assert store.questions(PROJECT) == []
    assert store.blocked_state_for(node_id, include_resolved=True) is None
    node = store.get_node(node_id)
    assert node is not None
    assert node.status is not NodeStatus.BLOCKED_ON_HUMAN
