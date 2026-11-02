"""D2: the PM's answer is settled inside ``acknowledge_resolution`` (slice 141)."""

from __future__ import annotations

import pytest
from question_harness import PROJECT, catch_for, make_slice, submit_resolution

from amoeba.runner.resolutions.vocabulary import ResolutionDecision
from amoeba.store import (
    AnsweredBy,
    BlockedKind,
    BlockEffect,
    DeclineReason,
    NodeStatus,
    QuestionRecord,
    QuestionState,
    ResolutionOutcome,
    StatusEffect,
    Store,
)

INSTRUCTIONS = "Use the target branch."
RESUME = ResolutionDecision.RESUME.value
STOP = ResolutionDecision.STOP.value
RE_BLOCK = BlockEffect("re-blocked", {"why": "test"})


def _ask(store: Store) -> tuple[str, QuestionRecord]:
    """A slice with a question block and its pending record."""
    node_id = make_slice(store)
    record = store.record_question(
        catch_for(store, node_id), block_context="ctx", block_payload=None
    )
    return node_id, record


def _reload(store: Store, record: QuestionRecord) -> QuestionRecord:
    found = store.question(record.id)
    assert found is not None
    return found


def _linked_block(record: QuestionRecord) -> str:
    assert record.blocked_state_id is not None
    return record.blocked_state_id


def _applied_resume(
    store: Store,
    record: QuestionRecord,
    *,
    instructions: str | None = None,
    submitted_by: str = "pm",
) -> None:
    block_id = _linked_block(record)
    submit_resolution(
        store,
        block_id,
        RESUME,
        instructions=instructions,
        submitted_by=submitted_by,
    )
    store.acknowledge_resolution(block_id, outcome=ResolutionOutcome.APPLIED)


def test_an_applied_resume_with_instructions_answers_a_pending_record(
    store: Store,
) -> None:
    _, record = _ask(store)

    _applied_resume(store, record, instructions=INSTRUCTIONS)

    answered = _reload(store, record)
    assert answered.state is QuestionState.ANSWERED
    assert answered.answered_by is AnsweredBy.PM
    assert answered.answer == INSTRUCTIONS
    assert answered.blocked_state_id == record.blocked_state_id


def test_an_applied_resume_answers_a_declined_record_and_keeps_the_reason(
    store: Store,
) -> None:
    _, record = _ask(store)
    store.decline_question(record.id, reason=DeclineReason.NO_ANSWER_ON_FILE)

    _applied_resume(store, record, instructions=INSTRUCTIONS)

    answered = _reload(store, record)
    assert answered.state is QuestionState.ANSWERED
    assert answered.answered_by is AnsweredBy.PM
    assert answered.answer == INSTRUCTIONS
    assert answered.decline_reason is DeclineReason.NO_ANSWER_ON_FILE


def test_an_applied_resume_without_instructions_answers_with_a_null_answer(
    store: Store,
) -> None:
    _, record = _ask(store)

    _applied_resume(store, record)

    answered = _reload(store, record)
    assert answered.state is QuestionState.ANSWERED
    assert answered.answered_by is AnsweredBy.PM
    assert answered.answer is None


@pytest.mark.parametrize(
    ("decision", "outcome", "code", "reason"),
    [
        (STOP, ResolutionOutcome.APPLIED, None, None),
        ("nonsense", ResolutionOutcome.REJECTED, "unknown_decision", "not a decision"),
    ],
    ids=["stop", "rejection"],
)
def test_a_re_block_moves_the_record_and_a_later_resume_answers_it(
    store: Store,
    decision: str,
    outcome: ResolutionOutcome,
    code: str | None,
    reason: str | None,
) -> None:
    node_id, record = _ask(store)
    first_block = _linked_block(record)
    submit_resolution(store, first_block, decision)

    store.acknowledge_resolution(
        first_block, outcome=outcome, code=code, reason=reason, effect=RE_BLOCK
    )

    moved = _reload(store, record)
    new_block = store.blocked_state_for(node_id)
    assert new_block is not None and new_block.id != first_block
    assert moved.state is QuestionState.PENDING
    assert moved.blocked_state_id == new_block.id
    _applied_resume(store, moved, instructions=INSTRUCTIONS)
    assert _reload(store, record).answer == INSTRUCTIONS


def test_an_applied_status_effect_leaves_the_record_unchanged(store: Store) -> None:
    node_id, record = _ask(store)
    block_id = _linked_block(record)
    submit_resolution(store, block_id, RESUME, instructions=INSTRUCTIONS)

    store.acknowledge_resolution(
        block_id,
        outcome=ResolutionOutcome.APPLIED,
        effect=StatusEffect(NodeStatus.IN_PROGRESS),
    )

    assert _reload(store, record) == record
    node = store.get_node(node_id)
    assert node is not None and node.status is NodeStatus.IN_PROGRESS


def test_an_answered_record_is_untouched_by_an_applied_resume(store: Store) -> None:
    _, record = _ask(store)
    # Stand in for 142's submission, which answers the record as the answerer.
    with store._connection:  # pyright: ignore[reportPrivateUsage]
        store._connection.execute(  # pyright: ignore[reportPrivateUsage]
            "UPDATE question_records SET state = 'answered', "
            "answered_by = 'answerer', answer = 'from the answerer' WHERE id = ?",
            (record.id,),
        )
    answered = _reload(store, record)

    _applied_resume(store, answered, instructions="pm words")

    assert _reload(store, record) == answered


def test_the_submitter_name_is_never_read(store: Store) -> None:
    _, record = _ask(store)
    store.decline_question(record.id, reason=DeclineReason.NO_ANSWER_ON_FILE)

    _applied_resume(
        store, record, instructions=INSTRUCTIONS, submitted_by="the-answerer"
    )

    assert _reload(store, record).answered_by is AnsweredBy.PM


def test_a_block_with_no_record_behaves_as_before(store: Store) -> None:
    node_id = make_slice(store)
    block = store.block(node_id, kind=BlockedKind.HUMAN, context="decide")
    submit_resolution(store, block.id, RESUME)

    store.acknowledge_resolution(block.id, outcome=ResolutionOutcome.APPLIED)

    assert store.questions(PROJECT) == []


def test_the_judge_produces_only_these_acknowledgment_shapes() -> None:
    """A new decision or shape must be given a rule in D2 before this passes."""
    assert {decision.value for decision in ResolutionDecision} == {RESUME, STOP}
    assert set(ResolutionOutcome) == {
        ResolutionOutcome.APPLIED,
        ResolutionOutcome.REJECTED,
    }
