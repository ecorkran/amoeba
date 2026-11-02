"""The ``questions`` listing and the question columns on ``blocked`` (slice 141)."""

from __future__ import annotations

from question_harness import PROJECT, catch_for, make_slice, seed_question

from amoeba.inspection import LISTINGS_BY_NAME
from amoeba.inspection.core import blocked_rows
from amoeba.inspection.listing import ListingRequest
from amoeba.inspection.questions import QUESTION_COLUMNS, question_rows
from amoeba.store import (
    AnsweredBy,
    BlockedKind,
    DeclineReason,
    QuestionRecord,
    QuestionState,
    Store,
)


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
