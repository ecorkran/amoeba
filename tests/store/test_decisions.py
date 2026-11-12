"""The decision reads (slice 224, 2.1): two programs, two members, several questions."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path

import pytest

from amoeba.answering.values import AnsweredBy, AnsweringEvidence
from amoeba.store.answers import add_pm_answer
from amoeba.store.decisions import answers_since, read_marker
from amoeba.store.store import Store
from store.decision_support import (
    CORE,
    FIRST,
    LINT,
    SECOND,
    THIRD,
    TOOLS,
    TRADING,
    at,
    automatic_answer,
    seed_programs,
    waiting_then_pm,
)
from store.question_support import NOW


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    with Store.open(tmp_path / "amoeba.sqlite3") as opened:
        seed_programs(opened)
        yield opened


@pytest.fixture
def seqs(store: Store) -> list[int]:
    """Three answers: trading automatic, tools PM, trading automatic."""
    return [
        automatic_answer(store, FIRST, CORE, 1),
        waiting_then_pm(store, SECOND, LINT, 2),
        automatic_answer(store, THIRD, CORE, 3),
    ]


def _listed(store: Store, **arguments: object) -> list[int]:
    with store.read() as transaction:
        return [row.answer.seq for row in answers_since(transaction, **arguments)]  # pyright: ignore[reportArgumentType]


def test_an_empty_store_has_marker_zero_and_no_answers(store: Store) -> None:
    with store.read() as transaction:
        assert read_marker(transaction) == 0
        assert answers_since(transaction, after_seq=0) == ()


def test_after_seq_lists_only_later_answers_in_seq_order(
    store: Store, seqs: list[int]
) -> None:
    assert _listed(store, after_seq=0) == seqs
    assert _listed(store, after_seq=seqs[0]) == seqs[1:]
    assert _listed(store, after_seq=seqs[2]) == []


def test_since_includes_the_answer_recorded_exactly_then(
    store: Store, seqs: list[int]
) -> None:
    assert _listed(store, since=at(2).isoformat()) == seqs[1:]
    assert (
        _listed(store, since=(at(2) + timedelta(microseconds=1)).isoformat())
        == (seqs[2:])
    )


def test_program_narrows_the_listing(store: Store, seqs: list[int]) -> None:
    assert _listed(store, after_seq=0, program=TRADING) == [seqs[0], seqs[2]]
    assert _listed(store, after_seq=0, program=TOOLS) == [seqs[1]]


def test_a_row_carries_answer_question_member_program_and_prior(
    store: Store, seqs: list[int]
) -> None:
    with store.read() as transaction:
        first, second, _third = answers_since(transaction, after_seq=0)

    assert first.answer.answered_by is AnsweredBy.ANSWERER
    assert first.answer.cited == ("r1",)
    assert first.question.key == FIRST
    assert first.question.member_id == CORE
    assert first.question.passages is not None
    assert first.program_id == TRADING
    assert first.prior_answer_seq is None
    assert second.answer.answered_by is AnsweredBy.PM
    assert second.question.waiting_detail == "limit 3"
    assert second.question.waiting_reason is not None
    assert second.program_id == TOOLS


def test_a_pm_answer_after_an_automatic_one_names_it_as_prior(store: Store) -> None:
    automatic = automatic_answer(store, FIRST, CORE, 1)
    with store.write() as transaction:
        override = add_pm_answer(transaction, FIRST, "pm says otherwise", now=at(2))

    with store.read() as transaction:
        rows = answers_since(transaction, after_seq=0)

    assert [row.answer.seq for row in rows] == [automatic, override]
    assert [row.prior_answer_seq for row in rows] == [None, automatic]
    assert rows[0].question.evidence == AnsweringEvidence(
        proposed_answer=None, cited=None, verdict="yes", reason="cited"
    )


def test_exactly_one_start_is_required(store: Store) -> None:
    with store.read() as transaction:
        with pytest.raises(ValueError, match="exactly one"):
            answers_since(transaction)
        with pytest.raises(ValueError, match="exactly one"):
            answers_since(transaction, after_seq=0, since=NOW.isoformat())
