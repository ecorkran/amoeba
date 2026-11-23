"""A served result survives its JSON document unchanged (slice 260, D11)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from store.decision_support import (
    CORE,
    FIRST,
    LINT,
    SECOND,
    THIRD,
    at,
    automatic_answer,
    seed_programs,
    waiting_then_pm,
)
from store.question_support import NOW, claimed_question
from store_open import open_local_store
from user_configs import user_config

from amoeba.operations.served import (
    ServedEdges,
    ServedResult,
    result_document,
    run_served,
)
from amoeba.operations.standing_models import StandingResult
from amoeba.store.questions import insert_question
from amoeba.store.store import Store
from amoeba.wiring_results import result_from_document


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    with open_local_store(tmp_path / "amoeba.sqlite3") as opened:
        seed_programs(opened)
        yield opened


def _run(store: Store, name: str, document: object) -> ServedResult:
    edges = ServedEdges(
        clock=lambda: NOW,
        load_config=user_config,
    )
    return run_served(name, store, document, edges)


def _round_trips(name: str, result: ServedResult) -> None:
    rebuilt = result_from_document(name, result_document(result))

    assert rebuilt == result


def test_representative_results_of_all_six_round_trip(store: Store) -> None:
    first = automatic_answer(store, FIRST, CORE, 1)
    pm_answer = waiting_then_pm(store, SECOND, LINT, 2)
    with store.write() as transaction:
        insert_question(transaction, claimed_question(THIRD, member_id=CORE), now=at(3))
    dismiss_document = {
        "run_id": THIRD.run_id,
        "paused_at": THIRD.paused_at,
        "reason": "no",
    }

    given = _run(store, "standing", {"text": "a rule"})
    assert isinstance(given, StandingResult)
    cases: list[tuple[str, ServedResult]] = [
        ("decisions", _run(store, "decisions", {})),
        ("decisions", _run(store, "decisions", {"since": "not a time"})),
        ("mark_read", _run(store, "mark_read", {"through": first})),
        ("mark_read", _run(store, "mark_read", {"through": first})),
        ("mark_read", _run(store, "mark_read", {"through": "x"})),
        ("standing", given),
        ("standing", _run(store, "standing", {"text": "a rule"})),
        ("standing", _run(store, "standing", {"text": "x", "member": "nobody"})),
        (
            "withdraw",
            _run(store, "withdraw", {"standing_id": given.standing_id, "reason": "r"}),
        ),
        ("withdraw", _run(store, "withdraw", {"standing_id": 999, "reason": "r"})),
        ("dismiss", _run(store, "dismiss", dismiss_document)),
        ("dismiss", _run(store, "dismiss", dismiss_document)),
        ("dismiss", _run(store, "dismiss", {"run_id": "no-such"})),
        ("retract", _run(store, "retract", {"answer_seq": pm_answer, "reason": "w"})),
        ("retract", _run(store, "retract", {"answer_seq": pm_answer, "reason": "w"})),
        ("retract", _run(store, "retract", {"answer_seq": 999, "reason": "w"})),
    ]

    for name, result in cases:
        _round_trips(name, result)


def test_a_decisions_listing_with_records_round_trips(store: Store) -> None:
    automatic_answer(store, FIRST, CORE, 1)
    waiting_then_pm(store, SECOND, LINT, 2)

    result = _run(store, "decisions", {})

    assert len(getattr(result, "records")) == 2  # noqa: B009
    _round_trips("decisions", result)


def test_an_unserved_name_cannot_be_rebuilt() -> None:
    with pytest.raises(ValueError, match="add"):
        result_from_document("add", {})


def test_a_document_that_is_not_that_result_is_a_value_error() -> None:
    with pytest.raises(ValueError, match="outcome"):
        result_from_document("mark_read", {"unrelated": 1})
