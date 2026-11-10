"""Answer reads and writes, the gated automatic settle and PM precedent
(slice 223, 1.8, 1.10 and 1.11)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path

import pytest

from amoeba.answering.values import (
    AnsweredBy,
    AnsweringEvidence,
    DeclineReason,
    GateRefusal,
)
from amoeba.store.answers import (
    Lost,
    Settled,
    add_pm_answer,
    answers_of,
    automatic_answer_count,
    latest_answer,
    pm_precedent,
    record_resume,
    settle_answered,
)
from amoeba.store.models import QuestionKey
from amoeba.store.questions import get_question, insert_question
from amoeba.store.store import Store
from amoeba.store.vocabulary import QuestionState, ResumeOutcome
from store.question_support import (
    ANSWERING_RUN,
    KEY,
    MEMBER_ID,
    NOW,
    OTHER_MEMBER_ID,
    claimed_question,
    seed_members,
    waiting_question,
)

EVIDENCE = AnsweringEvidence(proposed_answer="300", cited=("r1",), verdict="yes")
SECOND_KEY = QuestionKey(KEY.run_id, "2026-11-10T13:00:00+00:00")


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    with Store.open(tmp_path / "amoeba.sqlite3") as opened:
        seed_members(opened)
        yield opened


def _settle(
    store: Store,
    key: QuestionKey = KEY,
    gate_result: GateRefusal | None = None,
) -> Settled | GateRefusal | Lost:
    return settle_answered(
        store,
        key,
        ANSWERING_RUN,
        answer="300 lines",
        cited=("r1",),
        evidence=EVIDENCE,
        gate=lambda _prior: gate_result,
        now=NOW,
    )


def test_answers_come_back_in_seq_order_and_the_newest_is_latest(
    store: Store,
) -> None:
    with store.write() as transaction:
        insert_question(transaction, waiting_question(), now=NOW)
        first = add_pm_answer(transaction, KEY, "first", now=NOW)
        second = add_pm_answer(transaction, KEY, "second", now=NOW)

    with store.read() as transaction:
        rows = answers_of(transaction, KEY)
        newest = latest_answer(transaction, KEY)

    assert [row.seq for row in rows] == [first, second]
    assert [row.answer for row in rows] == ["first", "second"]
    assert newest is not None
    assert newest.seq == second


def test_latest_answer_is_none_without_answers(store: Store) -> None:
    with store.read() as transaction:
        assert latest_answer(transaction, KEY) is None
        assert answers_of(transaction, KEY) == ()


def test_automatic_count_ignores_pm_answers_and_spans_checkpoints(
    store: Store,
) -> None:
    with store.write() as transaction:
        insert_question(
            transaction, claimed_question(KEY, answering_run_id="a-1"), now=NOW
        )
        insert_question(
            transaction, claimed_question(SECOND_KEY, answering_run_id="a-2"), now=NOW
        )
    assert isinstance(
        settle_answered(
            store,
            KEY,
            "a-1",
            answer="x",
            cited=(),
            evidence=EVIDENCE,
            gate=lambda _prior: None,
            now=NOW,
        ),
        Settled,
    )
    assert isinstance(
        settle_answered(
            store,
            SECOND_KEY,
            "a-2",
            answer="y",
            cited=(),
            evidence=EVIDENCE,
            gate=lambda _prior: None,
            now=NOW,
        ),
        Settled,
    )
    with store.write() as transaction:
        add_pm_answer(transaction, KEY, "pm says", now=NOW)

    with store.read() as transaction:
        assert automatic_answer_count(transaction, KEY.run_id) == 2
        assert automatic_answer_count(transaction, "another-run") == 0


@pytest.mark.parametrize("seeded", ["claimed", "waiting"])
def test_a_pm_answer_sets_answered_and_keeps_the_waiting_reason(
    store: Store, seeded: str
) -> None:
    new = claimed_question() if seeded == "claimed" else waiting_question()
    with store.write() as transaction:
        insert_question(transaction, new, now=NOW)

    with store.write() as transaction:
        seq = add_pm_answer(transaction, KEY, "use 300", now=NOW)

    with store.read() as transaction:
        record = get_question(transaction, KEY)
        answer = latest_answer(transaction, KEY)
    assert record is not None
    assert record.state is QuestionState.ANSWERED
    assert record.waiting_reason is new.waiting_reason
    assert record.waiting_detail == new.waiting_detail
    assert answer is not None
    assert (answer.seq, answer.answered_by, answer.cited) == (seq, AnsweredBy.PM, None)


def test_record_resume_never_overwrites_resumed_or_not_delivered_but_does_refused(
    store: Store,
) -> None:
    with store.write() as transaction:
        insert_question(transaction, waiting_question(), now=NOW)
        seq = add_pm_answer(transaction, KEY, "use 300", now=NOW)

    def record(outcome: ResumeOutcome, detail: str) -> bool:
        with store.write() as transaction:
            return record_resume(
                transaction, seq, outcome, detail=detail, log="/log", at=NOW
            )

    def stored() -> tuple[ResumeOutcome | None, str | None]:
        with store.read() as transaction:
            row = latest_answer(transaction, KEY)
        assert row is not None
        return row.resume_outcome, row.resume_detail

    assert record(ResumeOutcome.REFUSED, "locked")
    assert stored() == (ResumeOutcome.REFUSED, "locked")
    assert record(ResumeOutcome.RESUMED, "ok")
    assert not record(ResumeOutcome.REFUSED, "late refusal")
    assert stored() == (ResumeOutcome.RESUMED, "ok")
    assert not record(ResumeOutcome.NOT_DELIVERED, "moved on")
    assert stored() == (ResumeOutcome.RESUMED, "ok")


def test_not_delivered_is_final_too(store: Store) -> None:
    with store.write() as transaction:
        insert_question(transaction, waiting_question(), now=NOW)
        seq = add_pm_answer(transaction, KEY, "use 300", now=NOW)
        assert record_resume(
            transaction, seq, ResumeOutcome.NOT_DELIVERED, detail=None, log=None, at=NOW
        )
        assert not record_resume(
            transaction, seq, ResumeOutcome.RESUMED, detail=None, log=None, at=NOW
        )


def test_a_successful_settle_writes_the_answerer_row_with_cited(store: Store) -> None:
    with store.write() as transaction:
        insert_question(transaction, claimed_question(), now=NOW)

    outcome = _settle(store)

    assert isinstance(outcome, Settled)
    with store.read() as transaction:
        record = get_question(transaction, KEY)
        answer = latest_answer(transaction, KEY)
    assert record is not None
    assert record.state is QuestionState.ANSWERED
    assert record.evidence == EVIDENCE
    assert answer is not None
    assert answer.seq == outcome.answer_seq
    assert answer.answered_by is AnsweredBy.ANSWERER
    assert answer.cited == ("r1",)


def test_a_pm_answer_during_the_claim_makes_the_settle_lost(store: Store) -> None:
    with store.write() as transaction:
        insert_question(transaction, claimed_question(), now=NOW)
        add_pm_answer(transaction, KEY, "pm first", now=NOW)

    assert isinstance(_settle(store), Lost)
    with store.read() as transaction:
        assert [row.answered_by for row in answers_of(transaction, KEY)] == [
            AnsweredBy.PM
        ]


def test_a_settle_for_another_claim_is_lost(store: Store) -> None:
    with store.write() as transaction:
        insert_question(
            transaction, claimed_question(answering_run_id="someone-else"), now=NOW
        )

    assert isinstance(_settle(store), Lost)


def test_a_declining_gate_writes_nothing_and_its_refusal_is_returned(
    store: Store,
) -> None:
    refusal = GateRefusal(DeclineReason.RESERVED_TERM, "push")
    with store.write() as transaction:
        insert_question(transaction, claimed_question(), now=NOW)

    assert _settle(store, gate_result=refusal) == refusal

    with store.read() as transaction:
        record = get_question(transaction, KEY)
        assert answers_of(transaction, KEY) == ()
    assert record is not None
    assert record.state is QuestionState.CLAIMED


def test_the_gate_counts_automatic_answers_only(store: Store) -> None:
    seen: list[int] = []
    with store.write() as transaction:
        insert_question(
            transaction, claimed_question(KEY, answering_run_id="a-1"), now=NOW
        )
        insert_question(transaction, waiting_question(SECOND_KEY), now=NOW)
        add_pm_answer(transaction, SECOND_KEY, "pm", now=NOW)

    def gate(prior: int) -> None:
        seen.append(prior)

    settle_answered(
        store, KEY, "a-1", answer="x", cited=(), evidence=EVIDENCE, gate=gate, now=NOW
    )

    assert seen == [0]


def _pm_answer(store: Store, key: QuestionKey, text: str, minutes: int) -> None:
    with store.write() as transaction:
        add_pm_answer(transaction, key, text, now=NOW + timedelta(minutes=minutes))


def test_precedent_is_the_newest_pm_answer_per_question(store: Store) -> None:
    with store.write() as transaction:
        insert_question(transaction, waiting_question(), now=NOW)
    _pm_answer(store, KEY, "older", 1)
    _pm_answer(store, KEY, "newer", 2)

    with store.read() as transaction:
        precedent = pm_precedent(transaction, MEMBER_ID)

    assert [item.answer for item in precedent] == ["newer"]
    assert precedent[0].question == "What is the file length limit?"
    assert precedent[0].key == KEY
    assert precedent[0].recorded_at == NOW + timedelta(minutes=2)


def test_an_automatic_only_question_is_no_precedent(store: Store) -> None:
    with store.write() as transaction:
        insert_question(transaction, claimed_question(), now=NOW)
    _settle(store)

    with store.read() as transaction:
        assert pm_precedent(transaction, MEMBER_ID) == ()


def test_precedent_excludes_other_members_and_keeps_slice_labels(store: Store) -> None:
    with store.write() as transaction:
        insert_question(transaction, claimed_question(), now=NOW)
        insert_question(
            transaction,
            waiting_question(SECOND_KEY, member_id=OTHER_MEMBER_ID),
            now=NOW,
        )
    _pm_answer(store, KEY, "mine", 1)
    _pm_answer(store, SECOND_KEY, "theirs", 2)

    with store.read() as transaction:
        mine = pm_precedent(transaction, MEMBER_ID)
        theirs = pm_precedent(transaction, OTHER_MEMBER_ID)

    assert [(item.answer, item.slice_label) for item in mine] == [
        ("mine", "223 pause-handling")
    ]
    assert [(item.answer, item.slice_label) for item in theirs] == [("theirs", None)]
