"""Question records: models, reads and ``decline_question`` (slice 141)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from question_harness import PROJECT, make_slice, seed_question

from amoeba.store import (
    QUESTION_TRANSITIONS,
    AnsweredBy,
    BlockedKind,
    DeclineReason,
    InvalidTransitionError,
    QuestionState,
    Store,
    UnknownVocabularyValueError,
    sql_questions,
)
from amoeba.store.mapping_questions import map_question_record


def test_every_state_has_a_transition_row_and_answered_is_terminal() -> None:
    assert set(QUESTION_TRANSITIONS) == set(QuestionState)
    assert QUESTION_TRANSITIONS[QuestionState.ANSWERED] == frozenset()
    assert QUESTION_TRANSITIONS[QuestionState.DECLINED] == {QuestionState.ANSWERED}


def test_an_unknown_stored_state_raises(store: Store) -> None:
    record = seed_question(store, make_slice(store))
    row = list(
        store._execute(  # pyright: ignore[reportPrivateUsage]
            sql_questions.SELECT_QUESTION_BY_ID, (record.id,)
        ).fetchone()
    )
    row[9] = "maybe"

    with pytest.raises(UnknownVocabularyValueError):
        map_question_record(row)


@pytest.mark.parametrize("column", [10, 12])
def test_an_unknown_answered_by_or_reason_raises(store: Store, column: int) -> None:
    record = seed_question(store, make_slice(store))
    row = list(
        store._execute(  # pyright: ignore[reportPrivateUsage]
            sql_questions.SELECT_QUESTION_BY_ID, (record.id,)
        ).fetchone()
    )
    row[column] = "nobody"

    with pytest.raises(UnknownVocabularyValueError):
        map_question_record(row)


def test_decline_from_pending_records_the_reason(store: Store) -> None:
    record = seed_question(store, make_slice(store))

    declined = store.decline_question(record.id, reason=DeclineReason.NO_ANSWER_ON_FILE)

    assert declined.state is QuestionState.DECLINED
    assert declined.decline_reason is DeclineReason.NO_ANSWER_ON_FILE
    assert declined.updated_at >= record.updated_at
    assert store.question(record.id) == declined


def test_decline_from_answered_raises_and_leaves_the_row(store: Store) -> None:
    record = seed_question(
        store,
        make_slice(store),
        state=QuestionState.ANSWERED,
        answered_by=AnsweredBy.PM,
        answer="use main",
    )

    with pytest.raises(InvalidTransitionError):
        store.decline_question(record.id, reason=DeclineReason.QUESTION_MISSING)

    assert store.question(record.id) == record


def test_decline_of_a_missing_record_raises(store: Store) -> None:
    with pytest.raises(InvalidTransitionError):
        store.decline_question("nope", reason=DeclineReason.QUESTION_MISSING)


def test_reads_filter_by_state_and_node_oldest_first(store: Store) -> None:
    first_slice = make_slice(store)
    second_slice = make_slice(store)
    first = seed_question(store, first_slice)
    second = seed_question(store, second_slice)
    third = seed_question(
        store,
        first_slice,
        state=QuestionState.DECLINED,
        decline_reason=DeclineReason.QUESTION_MISSING,
    )
    other_project = seed_question(store, make_slice(store, "other"), project_id="other")

    assert [r.id for r in store.questions(PROJECT)] == [first.id, second.id, third.id]
    assert [r.id for r in store.questions(PROJECT, node_id=first_slice)] == [
        first.id,
        third.id,
    ]
    assert [r.id for r in store.questions(PROJECT, state=QuestionState.DECLINED)] == [
        third.id
    ]
    assert [r.id for r in store.pending_questions(PROJECT)] == [first.id, second.id]
    assert [r.id for r in store.questions("other")] == [other_project.id]


def test_question_for_block_finds_the_linked_record(store: Store) -> None:
    node_id = make_slice(store)
    block = store.block(node_id, kind=BlockedKind.HUMAN, context="q")
    record = seed_question(store, node_id, blocked_state_id=block.id)

    assert store.question_for_block(block.id) == record
    assert store.question_for_block("nope") is None


def test_a_read_only_handle_can_call_the_reads(store_file: Path) -> None:
    with Store.open(store_file) as writer:
        node_id = make_slice(writer)
        record = seed_question(writer, node_id)

    with Store.open_read_only(store_file) as reader:
        assert reader.question(record.id) == record
        assert reader.questions(PROJECT) == [record]
        assert reader.pending_questions(PROJECT) == [record]
        assert reader.question_for_block("none") is None
        with pytest.raises(sqlite3.OperationalError):
            reader.decline_question(record.id, reason=DeclineReason.QUESTION_MISSING)
