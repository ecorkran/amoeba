"""The answering-run fields on a question record (slice 144, D8, D11)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from question_harness import make_slice, seed_question

from amoeba.store import (
    DeclineReason,
    PassageRef,
    Store,
    UnknownVocabularyValueError,
    sql_questions,
)
from amoeba.store.mapping_questions import (
    decode_passage_index,
    encode_passage_index,
    encode_text_list,
    map_question_record,
)

PM_DATE = datetime(2026, 10, 30, 9, 0, tzinfo=UTC)
PASSAGES = (
    PassageRef("P1", "docs/rules.md", None, datetime(2026, 11, 1, tzinfo=UTC)),
    PassageRef("P2", "q-17", "q-17", PM_DATE),
)


def test_a_record_holding_all_nine_fields_round_trips(store: Store) -> None:
    stored = seed_question(
        store,
        make_slice(store),
        answering={
            sql_questions.COL_QUESTION_SOURCE_COMMIT: "abc123",
            sql_questions.COL_QUESTION_PASSAGE_INDEX: encode_passage_index(PASSAGES),
            sql_questions.COL_QUESTION_DROPPED_PM_ANSWERS: encode_text_list(("q-3",)),
            sql_questions.COL_QUESTION_PROPOSED_ANSWER: "use main",
            sql_questions.COL_QUESTION_CITED_PASSAGES: encode_text_list(("P1", "P2")),
            sql_questions.COL_QUESTION_CHECK_VERDICT: "yes",
            sql_questions.COL_QUESTION_CHECK_REASON: "matches P1",
            sql_questions.COL_QUESTION_DECLINE_DETAIL: "detail",
        },
    )

    assert stored.source_commit == "abc123"
    assert stored.passage_index == PASSAGES
    assert stored.dropped_pm_answers == ("q-3",)
    assert stored.proposed_answer == "use main"
    assert stored.cited_passages == ("P1", "P2")
    assert stored.check_verdict == "yes"
    assert stored.check_reason == "matches P1"
    assert stored.decline_detail == "detail"
    assert stored.answering_entry_id is None


def test_a_record_written_before_015_maps_with_nones(store: Store) -> None:
    stored = seed_question(store, make_slice(store))

    assert [getattr(stored, name) for name in sql_questions.ANSWERING_COLUMNS] == [
        None
    ] * len(sql_questions.ANSWERING_COLUMNS)


@pytest.mark.parametrize("reason", list(DeclineReason))
def test_decline_question_accepts_every_reason(
    store: Store, reason: DeclineReason
) -> None:
    record = seed_question(store, make_slice(store))

    declined = store.decline_question(record.id, reason=reason)

    assert declined.decline_reason is reason


@pytest.mark.parametrize("stored", ["not json", '{"a": 1}', '[{"id": "P1"}]', "[1]"])
def test_a_malformed_passage_index_raises(stored: str) -> None:
    with pytest.raises(UnknownVocabularyValueError):
        decode_passage_index(stored)


def test_a_row_of_the_old_width_raises(store: Store) -> None:
    record = seed_question(store, make_slice(store))
    row = list(
        store._execute(  # pyright: ignore[reportPrivateUsage]
            sql_questions.SELECT_QUESTION_BY_ID, (record.id,)
        ).fetchone()
    )

    with pytest.raises(UnknownVocabularyValueError):
        map_question_record(row[:16])
