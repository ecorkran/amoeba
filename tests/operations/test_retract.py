"""``retract``, and what it does to precedent and ``decisions`` (slice 228, D6)."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
from datetime import timedelta
from pathlib import Path

import pytest
from store.decision_support import (
    CORE,
    FIRST,
    LINT,
    SECOND,
    at,
    automatic_answer,
    seed_programs,
    waiting_then_pm,
)
from store.question_support import NOW, waiting_question

from amoeba.operations.decisions import DecisionsOutcome, DecisionsResult, decisions
from amoeba.operations.dismiss import DismissOutcome, dismiss
from amoeba.operations.retract import (
    RetractOutcome,
    RetractRejection,
    RetractResult,
    retract,
)
from amoeba.store.answers import add_pm_answer, pm_precedent
from amoeba.store.decisions import advance_marker, read_marker
from amoeba.store.models import QuestionKey
from amoeba.store.questions import insert_question
from amoeba.store.store import Store
from amoeba.upstream.context_forge.projects import ProjectNames
from operations.pause_support import build_deps

NAMES: ProjectNames = {CORE: "core-name", LINT: "lint-name"}
LATER = NOW + timedelta(hours=1)
REASON = "wrong number"


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    with Store.open(tmp_path / "amoeba.sqlite3") as opened:
        seed_programs(opened)
        yield opened


def _retract(store: Store, seq: object, reason: object = REASON) -> RetractResult:
    return retract(store, {"answer_seq": seq, "reason": reason}, clock=lambda: LATER)


def _decisions(store: Store, tmp_path: Path) -> DecisionsResult:
    rig = build_deps(tmp_path, polls={}, spawns=[])
    deps = replace(rig.deps, project_names=lambda: NAMES)
    return decisions(store, {}, deps=deps)


def _precedent(store: Store, member: str = LINT) -> list[str]:
    with store.read() as transaction:
        return [item.answer for item in pm_precedent(transaction, member)]


def test_it_retracts_a_pm_answer_and_the_answer_leaves_precedent(
    store: Store,
) -> None:
    seq = waiting_then_pm(store, SECOND, LINT, 2)
    assert _precedent(store) == [f"pm {SECOND.run_id}"]

    result = _retract(store, seq)

    assert result.outcome is RetractOutcome.RETRACTED
    assert result.answer_seq == seq
    assert result.key == SECOND
    assert _precedent(store) == []


def test_a_repeat_is_unchanged(store: Store) -> None:
    seq = waiting_then_pm(store, SECOND, LINT, 2)
    _retract(store, seq)

    again = _retract(store, seq, "second thoughts")

    assert again.outcome is RetractOutcome.UNCHANGED


def test_an_automatic_answer_is_rejected(store: Store) -> None:
    seq = automatic_answer(store, FIRST, CORE, 1)

    result = _retract(store, seq)

    assert result.outcome is RetractOutcome.REJECTED
    assert result.rejection is RetractRejection.NOT_A_PM_ANSWER


def test_an_unknown_answer_is_rejected(store: Store) -> None:
    result = _retract(store, 999)

    assert result.rejection is RetractRejection.NO_SUCH_ANSWER


@pytest.mark.parametrize(
    "document",
    [
        {"answer_seq": 1, "reason": "   "},
        {"answer_seq": 1},
        {"reason": "x"},
        {"answer_seq": "1", "reason": "x"},
        {"answer_seq": 1.5, "reason": "x"},
        {"answer_seq": True, "reason": "x"},
        {"answer_seq": 1, "reason": "x", "extra": 1},
        "not a mapping",
        None,
    ],
)
def test_a_malformed_document_is_rejected(store: Store, document: object) -> None:
    result = retract(store, document, clock=lambda: LATER)

    assert result.outcome is RetractOutcome.REJECTED
    assert result.rejection is RetractRejection.MALFORMED
    assert result.problems


def test_a_new_pm_answer_to_the_same_question_restores_precedent(
    store: Store,
) -> None:
    seq = waiting_then_pm(store, SECOND, LINT, 2)
    _retract(store, seq)
    with store.write() as transaction:
        add_pm_answer(transaction, SECOND, "the corrected answer", now=at(3))

    assert _precedent(store) == ["the corrected answer"]


def test_decisions_shows_the_retraction_and_keeps_the_answer_listed(
    store: Store, tmp_path: Path
) -> None:
    seq = waiting_then_pm(store, SECOND, LINT, 2)
    _retract(store, seq)

    result = _decisions(store, tmp_path)

    (record,) = result.records
    assert record.seq == seq
    assert record.retracted_at == LATER
    assert record.retract_reason == REASON


def test_closures_are_not_listed_and_the_marker_and_read_through_are_unchanged(
    store: Store, tmp_path: Path
) -> None:
    first = automatic_answer(store, FIRST, CORE, 1)
    seq = waiting_then_pm(store, SECOND, LINT, 2)
    other = QuestionKey("run-closed", "2026-11-10T12:00:00+00:00")
    with store.write() as transaction:
        insert_question(transaction, waiting_question(other, member_id=LINT), now=NOW)
    advance_marker(store, first)
    before = _decisions(store, tmp_path)
    assert before.outcome is DecisionsOutcome.LISTED

    closed = dismiss(
        store, {"run_id": other.run_id, "reason": "x"}, clock=lambda: LATER
    )
    _retract(store, seq)
    after = _decisions(store, tmp_path)

    assert closed.outcome is DismissOutcome.DISMISSED
    assert [record.seq for record in after.records] == [
        seq
    ]  # the closure is not listed
    assert after.read_through == before.read_through == seq
    assert after.marker == before.marker == first
    with store.read() as transaction:
        assert read_marker(transaction) == first
