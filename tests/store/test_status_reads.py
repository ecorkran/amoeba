"""The question reads behind ``status`` (slice 224, 3.3)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path

import pytest

from amoeba.store.answers import add_pm_answer
from amoeba.store.models import QuestionKey
from amoeba.store.questions import (
    insert_question,
    latest_rows_by_run,
    open_questions,
)
from amoeba.store.store import Store
from store.question_support import (
    MEMBER_ID,
    NOW,
    OTHER_MEMBER_ID,
    claimed_question,
    seed_members,
    waiting_question,
)

EARLY = QuestionKey("run-a", "2026-11-10T08:00:00+00:00")
LATE = QuestionKey("run-a", "2026-11-10T09:00:00+00:00")
OTHER_RUN = QuestionKey("run-b", "2026-11-10T10:00:00+00:00")
FOREIGN = QuestionKey("run-c", "2026-11-10T11:00:00+00:00")


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    with Store.open(tmp_path / "amoeba.sqlite3") as opened:
        seed_members(opened)
        yield opened


def test_open_questions_are_the_waiting_rows_of_the_given_members_oldest_first(
    store: Store,
) -> None:
    with store.write() as transaction:
        insert_question(
            transaction,
            waiting_question(LATE, member_id=MEMBER_ID),
            now=NOW + timedelta(minutes=2),
        )
        insert_question(
            transaction,
            waiting_question(EARLY, member_id=MEMBER_ID),
            now=NOW + timedelta(minutes=1),
        )
        insert_question(
            transaction, claimed_question(OTHER_RUN, member_id=MEMBER_ID), now=NOW
        )
        insert_question(
            transaction, waiting_question(FOREIGN, member_id=OTHER_MEMBER_ID), now=NOW
        )
        answered = QuestionKey("run-d", "2026-11-10T12:00:00+00:00")
        insert_question(
            transaction, waiting_question(answered, member_id=MEMBER_ID), now=NOW
        )
        add_pm_answer(transaction, answered, "ok", now=NOW)

    with store.read() as transaction:
        opened = open_questions(transaction, [MEMBER_ID])
        both = open_questions(transaction, [MEMBER_ID, OTHER_MEMBER_ID])
        none = open_questions(transaction, [])

    assert [row.key for row in opened] == [EARLY, LATE]
    assert opened[0].slice_label is None
    assert opened[0].waiting_detail == "limit 3"
    assert opened[0].claimed_at == NOW + timedelta(minutes=1)
    assert {row.key for row in both} == {EARLY, LATE, FOREIGN}
    assert none == ()


def test_the_latest_row_of_a_run_is_the_newer_question_with_its_latest_answer(
    store: Store,
) -> None:
    with store.write() as transaction:
        insert_question(transaction, claimed_question(EARLY), now=NOW)
        add_pm_answer(transaction, EARLY, "old answer", now=NOW)
        insert_question(
            transaction, waiting_question(LATE), now=NOW + timedelta(minutes=5)
        )
        add_pm_answer(transaction, LATE, "first", now=NOW + timedelta(minutes=6))
        newest = add_pm_answer(
            transaction, LATE, "second", now=NOW + timedelta(minutes=7)
        )
        insert_question(transaction, claimed_question(OTHER_RUN), now=NOW)
        insert_question(
            transaction, claimed_question(FOREIGN, member_id=OTHER_MEMBER_ID), now=NOW
        )

    with store.read() as transaction:
        found = latest_rows_by_run(transaction, [MEMBER_ID])
        nobody = latest_rows_by_run(transaction, [])

    assert set(found) == {"run-a", "run-b"}
    row, answer = found["run-a"]
    assert row.key == LATE
    assert answer is not None
    assert (answer.seq, answer.answer) == (newest, "second")
    run_b_row, run_b_answer = found["run-b"]
    assert run_b_row.key == OTHER_RUN
    assert run_b_answer is None
    assert nobody == {}
