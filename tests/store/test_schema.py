"""The baseline schema's constraints, and the seed helpers that exercise them."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from amoeba.answering.values import AnsweredBy
from amoeba.store.errors import StoreIntegrityError
from amoeba.store.store import Store, Transaction
from amoeba.store.vocabulary import ConsumedMode, QuestionState
from store.seed import (
    insert_answer,
    insert_member,
    insert_pair,
    insert_program,
    insert_question,
)

NOW = datetime(2026, 11, 9, 12, 0, tzinfo=UTC)
TABLES = {
    "schema_meta",
    "programs",
    "members",
    "dependency_pairs",
    "releases",
    "questions",
    "answers",
    "pm_marker",
}


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    with Store.open(tmp_path / "amoeba.sqlite3") as opened:
        yield opened


def _program(transaction: Transaction, program_id: str) -> None:
    insert_program(
        transaction,
        program_id=program_id,
        concept_member=None,
        concept_path=None,
        registered_at=NOW,
        updated_at=NOW,
    )


def _member(transaction: Transaction, project_id: str, program_id: str) -> None:
    insert_member(
        transaction,
        project_id=project_id,
        program_id=program_id,
        rules_paths=("CLAUDE.md",),
        authorize_allow=(),
        authorize_deny=(),
        registered_at=NOW,
        updated_at=NOW,
    )


def _pair(
    transaction: Transaction, program_id: str, provider_id: str, consumer_id: str
) -> None:
    insert_pair(
        transaction,
        program_id=program_id,
        provider_id=provider_id,
        consumer_id=consumer_id,
        consumed=ConsumedMode.FROM_SOURCE,
        registered_at=NOW,
        updated_at=NOW,
    )


def test_a_new_store_has_all_eight_tables(store: Store) -> None:
    with store.read() as transaction:
        names = {
            row[0]
            for row in transaction.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
                " AND name NOT LIKE 'sqlite_%'"
            )
        }

    assert names == TABLES


def test_pm_marker_holds_one_row_at_zero(store: Store) -> None:
    with store.read() as transaction:
        rows = transaction.execute("SELECT id, last_seen_seq FROM pm_marker").fetchall()

    assert [tuple(row) for row in rows] == [(1, 0)]


def test_a_pair_cannot_cross_programs(store: Store) -> None:
    with pytest.raises(StoreIntegrityError), store.write() as transaction:
        _program(transaction, "one")
        _program(transaction, "two")
        _member(transaction, "a", "one")
        _member(transaction, "b", "two")
        _pair(transaction, "one", "a", "b")


def test_a_pair_cannot_have_equal_ends(store: Store) -> None:
    with pytest.raises(StoreIntegrityError), store.write() as transaction:
        _program(transaction, "one")
        _member(transaction, "a", "one")
        _pair(transaction, "one", "a", "a")


def test_a_member_needs_an_existing_program(store: Store) -> None:
    with pytest.raises(StoreIntegrityError), store.write() as transaction:
        _member(transaction, "a", "missing")


def test_seeded_rows_read_back(store: Store) -> None:
    with store.write() as transaction:
        _program(transaction, "demo")
        _member(transaction, "provider", "demo")
        _member(transaction, "consumer", "demo")
        _pair(transaction, "demo", "provider", "consumer")
        insert_question(
            transaction,
            run_id="run-1",
            paused_at="2026-11-09T12:00:00Z",
            member_id="consumer",
            question="Which branch?",
            checkout="/work/consumer",
            state=QuestionState.CLAIMED,
            answering_run_id=None,
            waiting_reason=None,
            claimed_at=NOW,
            updated_at=NOW,
        )
        insert_answer(
            transaction,
            run_id="run-1",
            paused_at="2026-11-09T12:00:00Z",
            answered_by=AnsweredBy.ANSWERER,
            answer="main",
            recorded_at=NOW,
            resume_outcome=None,
        )

    with store.read() as transaction:
        pair = transaction.execute(
            "SELECT provider_id, consumer_id, consumed FROM dependency_pairs"
        ).fetchone()
        question = transaction.execute(
            "SELECT member_id, state FROM questions WHERE run_id = 'run-1'"
        ).fetchone()
        answer = transaction.execute(
            "SELECT answered_by, answer FROM answers WHERE run_id = 'run-1'"
        ).fetchone()

    assert tuple(pair) == ("provider", "consumer", "from_source")
    assert tuple(question) == ("consumer", "claimed")
    assert tuple(answer) == ("answerer", "main")
