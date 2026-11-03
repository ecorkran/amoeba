"""The ``questions`` listing and the question columns on ``blocked`` (slice 141)."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from question_harness import PROJECT, catch_for, make_slice, seed_question

from amoeba.inspection import LISTINGS_BY_NAME
from amoeba.inspection.core import blocked_rows
from amoeba.inspection.listing import ListingRequest
from amoeba.inspection.questions import QUESTION_COLUMNS, question_rows
from amoeba.store import (
    AnsweredBy,
    BlockedKind,
    CommandKind,
    DeclineReason,
    PassageRef,
    QuestionRecord,
    QuestionState,
    Store,
    sql_questions,
)
from amoeba.store.mapping_questions import encode_passage_index, encode_text_list


def _request(**options: str | None) -> ListingRequest:
    values: dict[str, str | None] = {"node": None, "state": None, **options}
    return ListingRequest(project_id=PROJECT, options=values, compact=False)


def _seed_each_state(store: Store) -> dict[QuestionState, QuestionRecord]:
    node_id = make_slice(store)
    return {
        QuestionState.PENDING: seed_question(store, node_id),
        QuestionState.DECLINED: seed_question(
            store,
            node_id,
            state=QuestionState.DECLINED,
            decline_reason=DeclineReason.NO_ANSWER_ON_FILE,
            truncated=True,
        ),
        QuestionState.ANSWERED: seed_question(
            store,
            node_id,
            state=QuestionState.ANSWERED,
            answered_by=AnsweredBy.PM,
            answer="use main",
        ),
    }


def test_the_listing_declares_its_columns_and_options() -> None:
    listing = LISTINGS_BY_NAME["questions"]

    assert listing.columns == QUESTION_COLUMNS
    assert [option.name for option in listing.value_options] == ["node"]
    assert [option.name for option in listing.choice_options] == ["state"]
    assert listing.choice_options[0].choices == tuple(s.value for s in QuestionState)


def test_rows_show_state_answerer_and_outcome_for_each_state(store: Store) -> None:
    _seed_each_state(store)

    by_state = {row["state"]: row for row in question_rows(store, _request())}

    assert by_state["pending"]["outcome"] == ""
    assert by_state["pending"]["answered_by"] == ""
    assert by_state["declined"]["outcome"] == "no_answer_on_file"
    assert by_state["declined"]["truncated"] is True
    assert by_state["answered"]["outcome"] == "use main"
    assert by_state["answered"]["answered_by"] == "pm"


def test_a_reserved_term_decline_shows_the_term_as_configured(store: Store) -> None:
    node_id = make_slice(store)
    seed_question(
        store,
        node_id,
        state=QuestionState.DECLINED,
        decline_reason=DeclineReason.RESERVED_TERM,
        reserved_term="Force Push",
    )
    seed_question(
        store,
        node_id,
        state=QuestionState.DECLINED,
        decline_reason=DeclineReason.ANSWER_LIMIT_REACHED,
    )
    seed_question(store, node_id)

    rows = question_rows(store, _request())

    assert sorted(str(row["reserved_term"]) for row in rows) == ["", "", "Force Push"]
    [term_row] = [row for row in rows if row["reserved_term"]]
    assert term_row["outcome"] == "reserved_term"


def test_a_node_lists_every_record_and_both_answerer_answers(store: Store) -> None:
    node_id = make_slice(store)
    for answer in ("use main", "squash"):
        seed_question(
            store,
            node_id,
            state=QuestionState.ANSWERED,
            answered_by=AnsweredBy.ANSWERER,
            answer=answer,
        )
    seed_question(
        store,
        node_id,
        state=QuestionState.DECLINED,
        decline_reason=DeclineReason.ANSWER_LIMIT_REACHED,
    )

    rows = question_rows(store, _request(node=node_id))

    assert len(rows) == 3
    answered = [row for row in rows if row["state"] == "answered"]
    assert {row["outcome"] for row in answered} == {"use main", "squash"}
    assert {row["answered_by"] for row in answered} == {"answerer"}


def test_the_row_carries_the_json_only_fields_after_the_columns(
    store: Store,
) -> None:
    record = _seed_each_state(store)[QuestionState.PENDING]

    [row] = question_rows(store, _request(state="pending"))

    assert tuple(row)[: len(QUESTION_COLUMNS)] == QUESTION_COLUMNS
    assert row["source_entry_id"] == record.source_entry_id
    assert row["blocked_state_id"] is None
    assert row["updated_at"]


def test_state_and_node_filter(store: Store) -> None:
    records = _seed_each_state(store)
    other = seed_question(store, make_slice(store))

    declined = question_rows(store, _request(state="declined"))
    on_other = question_rows(store, _request(node=other.node_id))

    assert [row["id"] for row in declined] == [records[QuestionState.DECLINED].id]
    assert [row["id"] for row in on_other] == [other.id]


def test_blocked_shows_the_question_columns_and_empties_for_another_block(
    store: Store,
) -> None:
    asking = make_slice(store)
    record = store.record_question(
        catch_for(store, asking), block_context="q", block_payload=None
    )
    store.decline_question(record.id, reason=DeclineReason.ANSWERER_NOT_CONFIGURED)
    plain = make_slice(store)
    store.block(plain, kind=BlockedKind.JUDGE, context="needs a verdict")

    rows = {row["node_id"]: row for row in blocked_rows(store, _request())}

    assert rows[asking]["question_state"] == "declined"
    assert rows[asking]["decline_reason"] == "answerer_not_configured"
    assert rows[asking]["question_id"] == record.id
    assert rows[plain]["question_state"] == ""
    assert rows[plain]["decline_reason"] == ""
    assert rows[plain]["question_id"] == ""


def test_the_blocked_listing_declares_the_new_columns_last() -> None:
    columns = LISTINGS_BY_NAME["blocked"].columns

    assert columns[-2:] == ("question_state", "decline_reason")


# --------------------------------------------------------------------------
# The answering-run columns (slice 144, D11)
# --------------------------------------------------------------------------

RUN_ID = "run-20261103-listing-0001"
PASSAGES = (
    PassageRef("P1", "docs/rules.md", None, datetime(2026, 11, 1, tzinfo=UTC)),
    PassageRef("P2", "q-7", "q-7", datetime(2026, 10, 30, tzinfo=UTC)),
)


def _answering_entry_id(store: Store, node_id: str) -> str:
    return store.journal_issue(
        node_id,
        kind=CommandKind.SQ_ANSWER,
        parameters={
            "run_id": RUN_ID,
            "pipeline": "answering.yaml",
            "params": {},
            "scratch": "/tmp/answering/x",
        },
    ).id


def _answering_columns(entry_id: str, **extra: str | None) -> dict[str, object]:
    base: dict[str, object] = {
        sql_questions.COL_QUESTION_ANSWERING_ENTRY_ID: entry_id,
        sql_questions.COL_QUESTION_SOURCE_COMMIT: "abc123",
        sql_questions.COL_QUESTION_PASSAGE_INDEX: encode_passage_index(PASSAGES),
        sql_questions.COL_QUESTION_DROPPED_PM_ANSWERS: encode_text_list(("q-3",)),
        sql_questions.COL_QUESTION_PROPOSED_ANSWER: "use main",
        sql_questions.COL_QUESTION_CITED_PASSAGES: encode_text_list(("P1", "P2")),
        sql_questions.COL_QUESTION_CHECK_VERDICT: "yes",
        sql_questions.COL_QUESTION_CHECK_REASON: "matches P1",
    }
    return {**base, **extra}


def test_the_table_columns_include_the_run_the_verdict_and_the_detail() -> None:
    assert QUESTION_COLUMNS[-3:] == (
        "answering_run_id",
        "check_verdict",
        "decline_detail",
    )


def test_an_answered_record_shows_the_run_id_verdict_and_citations(
    store: Store,
) -> None:
    node_id = make_slice(store)
    entry_id = _answering_entry_id(store, node_id)
    seed_question(
        store,
        node_id,
        state=QuestionState.ANSWERED,
        answered_by=AnsweredBy.ANSWERER,
        answer="use main",
        answering=_answering_columns(entry_id),
    )

    [row] = question_rows(store, _request())

    assert row["answering_run_id"] == RUN_ID
    assert row["check_verdict"] == "yes"
    assert row["cited_passages"] == ["P1", "P2"]
    assert row["check_reason"] == "matches P1"
    assert row["decline_detail"] == ""


def test_a_declined_record_shows_the_detail_and_the_proposed_answer(
    store: Store,
) -> None:
    node_id = make_slice(store)
    entry_id = _answering_entry_id(store, node_id)
    seed_question(
        store,
        node_id,
        state=QuestionState.DECLINED,
        decline_reason=DeclineReason.CHECK_SAID_NO,
        answering=_answering_columns(
            entry_id,
            **{
                sql_questions.COL_QUESTION_DECLINE_DETAIL: "the check disagreed",
                sql_questions.COL_QUESTION_CHECK_VERDICT: "no",
            },
        ),
    )

    [row] = question_rows(store, _request())

    assert row["decline_detail"] == "the check disagreed"
    assert row["proposed_answer"] == "use main"
    assert row["check_verdict"] == "no"
    assert row["outcome"] == "check_said_no"


def test_a_record_written_before_015_lists_with_empty_values(store: Store) -> None:
    seed_question(store, make_slice(store))

    [row] = question_rows(store, _request())

    assert row["answering_run_id"] == ""
    assert row["check_verdict"] == ""
    assert row["decline_detail"] == ""
    assert row["passage_index"] is None
    assert row["cited_passages"] is None
    assert row["dropped_pm_answers"] is None


def test_json_rows_hold_the_passage_index_with_source_and_date(store: Store) -> None:
    node_id = make_slice(store)
    seed_question(
        store,
        node_id,
        answering=_answering_columns(_answering_entry_id(store, node_id)),
    )

    [row] = question_rows(store, _request())

    assert row["source_commit"] == "abc123"
    assert row["dropped_pm_answers"] == ["q-3"]
    assert row["passage_index"] == [
        {
            "id": "P1",
            "source": "docs/rules.md",
            "question_id": None,
            "date": "2026-11-01T00:00:00+00:00",
        },
        {
            "id": "P2",
            "source": "q-7",
            "question_id": "q-7",
            "date": "2026-10-30T00:00:00+00:00",
        },
    ]
    assert json.dumps(row)  # the row is plain JSON
