"""``set_up`` ``remove``: members soft-removed, pairs deleted, open questions block."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from store.question_support import NOW, claimed_question, waiting_question
from store.seed import insert_member

from amoeba.operations.dismiss import dismiss
from amoeba.operations.set_up_models import (
    SetUpOutcome,
    SetUpProblemCode,
    SetUpResult,
)
from amoeba.store.answers import add_pm_answer
from amoeba.store.models import QuestionKey
from amoeba.store.programs import get_member_any, get_pair, get_program
from amoeba.store.questions import insert_question
from amoeba.store.store import Store
from operations.set_up_support import run_set_up

PROJECTS = [
    ("provider-id", "provider"),
    ("consumer-id", "consumer"),
    ("other-id", "other"),
]
RULES = {"rules_paths": ["CLAUDE.md"]}
CLAIMED = QuestionKey("run-claimed", "2026-11-10T11:00:00+00:00")
WAITING = QuestionKey("run-waiting", "2026-11-10T11:05:00+00:00")
ANSWERED = QuestionKey("run-answered", "2026-11-10T11:10:00+00:00")
CONCEPT = {"member": "consumer", "path": "docs/concept.md"}
REMOVE_CONSUMER = {"program": "demo", "remove": {"members": ["consumer"]}}


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    with Store.open(tmp_path / "amoeba.sqlite3") as opened:
        first = run_set_up(opened, _program(), projects=PROJECTS)
        assert first.outcome is SetUpOutcome.APPLIED
        yield opened


def _program(**extra: Any) -> dict[str, Any]:
    """Provider and a consumer that depends on it."""
    return {
        "program": "demo",
        "members": [
            {"project": "provider", **RULES},
            {
                "project": "consumer",
                **RULES,
                "depends_on": [{"provider": "provider", "consumed": "from_source"}],
            },
        ],
        **extra,
    }


def _set_up(store: Store, document: dict[str, Any]) -> SetUpResult:
    return run_set_up(store, document, projects=PROJECTS)


def _codes(result: SetUpResult) -> list[SetUpProblemCode]:
    return [problem.code for problem in result.problems]


def _removed_at(store: Store, project_id: str) -> object:
    with store.read() as transaction:
        member = get_member_any(transaction, project_id)
    assert member is not None
    return member.removed_at


def _open_question(store: Store, key: QuestionKey, *, waiting: bool) -> None:
    question = (
        waiting_question(key, member_id="consumer-id")
        if waiting
        else claimed_question(key, member_id="consumer-id")
    )
    with store.write() as transaction:
        insert_question(transaction, question, now=NOW)


def _dismiss(store: Store, key: QuestionKey) -> None:
    result = dismiss(
        store,
        {"run_id": key.run_id, "reason": "not needed"},
        clock=lambda: NOW,
    )
    assert result.outcome.value in ("dismissed", "unchanged"), result


def test_removes_a_pair_then_a_member_and_a_repeat_is_unchanged(store: Store) -> None:
    pair = {"provider": "provider", "consumer": "consumer"}

    pair_result = _set_up(store, {"program": "demo", "remove": {"pairs": [pair]}})
    member_result = _set_up(store, REMOVE_CONSUMER)
    repeat = _set_up(store, REMOVE_CONSUMER)

    assert pair_result.outcome is SetUpOutcome.APPLIED
    assert pair_result.changes == ("removed pair provider-id -> consumer-id",)
    assert member_result.changes == ("removed member consumer-id",)
    assert member_result.program is not None
    assert [m.project_id for m in member_result.program.members] == ["provider-id"]
    assert repeat.outcome is SetUpOutcome.UNCHANGED
    assert repeat.changes == ()
    with store.read() as transaction:
        assert get_pair(transaction, "provider-id", "consumer-id") is None
    assert _removed_at(store, "consumer-id") is not None


def test_removing_a_member_takes_its_pairs_with_it(store: Store) -> None:
    result = _set_up(store, {"program": "demo", "remove": {"members": ["provider"]}})

    assert result.changes == ("removed member provider-id",)
    with store.read() as transaction:
        assert get_pair(transaction, "provider-id", "consumer-id") is None


def test_removing_an_absent_pair_between_members_changes_nothing(store: Store) -> None:
    result = _set_up(
        store,
        {
            "program": "demo",
            "remove": {"pairs": [{"provider": "consumer", "consumer": "provider"}]},
        },
    )

    assert result.outcome is SetUpOutcome.UNCHANGED


def test_naming_a_removed_member_re_adds_it_and_needs_rules_paths(
    store: Store,
) -> None:
    _set_up(store, REMOVE_CONSUMER)

    without_rules = _set_up(
        store, {"program": "demo", "members": [{"project": "consumer"}]}
    )
    with_rules = _set_up(
        store, {"program": "demo", "members": [{"project": "consumer", **RULES}]}
    )

    assert _codes(without_rules) == [SetUpProblemCode.RULES_PATHS_REQUIRED]
    assert with_rules.changes == ("added member consumer-id",)
    assert _removed_at(store, "consumer-id") is None


def test_a_removed_member_can_join_another_program(store: Store) -> None:
    _set_up(store, REMOVE_CONSUMER)

    result = _set_up(
        store, {"program": "elsewhere", "members": [{"project": "consumer", **RULES}]}
    )

    assert result.outcome is SetUpOutcome.APPLIED
    assert result.program is not None
    assert [m.project_id for m in result.program.members] == ["consumer-id"]
    with store.read() as transaction:
        member = get_member_any(transaction, "consumer-id")
    assert member is not None
    assert member.program_id == "elsewhere"


def test_open_questions_block_the_removal_until_dismissed(store: Store) -> None:
    _open_question(store, CLAIMED, waiting=False)
    _open_question(store, WAITING, waiting=True)

    blocked = _set_up(store, REMOVE_CONSUMER)

    assert _codes(blocked) == [SetUpProblemCode.MEMBER_HAS_OPEN_QUESTIONS]
    detail = blocked.problems[0].detail
    assert CLAIMED.run_id in detail
    assert WAITING.run_id in detail
    assert "dismiss" in detail
    assert _removed_at(store, "consumer-id") is None

    _dismiss(store, CLAIMED)
    _dismiss(store, WAITING)

    assert _set_up(store, REMOVE_CONSUMER).changes == ("removed member consumer-id",)


def test_an_answer_not_yet_handed_over_blocks_the_removal_too(store: Store) -> None:
    _open_question(store, ANSWERED, waiting=True)
    with store.write() as transaction:
        add_pm_answer(transaction, ANSWERED, "an answer", now=NOW, via=None)

    blocked = _set_up(store, REMOVE_CONSUMER)

    assert _codes(blocked) == [SetUpProblemCode.MEMBER_HAS_OPEN_QUESTIONS]
    assert ANSWERED.run_id in blocked.problems[0].detail

    _dismiss(store, ANSWERED)

    assert _set_up(store, REMOVE_CONSUMER).outcome is SetUpOutcome.APPLIED


def test_a_reference_that_is_no_member_is_not_a_member(store: Store) -> None:
    by_name = _set_up(store, {"program": "demo", "remove": {"members": ["other"]}})
    unknown = _set_up(store, {"program": "demo", "remove": {"members": ["stranger"]}})
    bad_pair = _set_up(
        store,
        {
            "program": "demo",
            "remove": {"pairs": [{"provider": "other", "consumer": "consumer"}]},
        },
    )

    assert _codes(by_name) == [SetUpProblemCode.NOT_A_MEMBER]
    assert _codes(unknown) == [SetUpProblemCode.NOT_A_MEMBER]
    assert "Context Forge has no such project" in unknown.problems[0].detail
    assert _codes(bad_pair) == [SetUpProblemCode.NOT_A_MEMBER]
    assert "remove.pairs.0.provider" in bad_pair.problems[0].detail


def test_a_member_of_another_program_is_not_a_member_of_this_one(store: Store) -> None:
    _set_up(store, {"program": "elsewhere", "members": [{"project": "other", **RULES}]})

    result = _set_up(store, {"program": "demo", "remove": {"members": ["other"]}})

    assert _codes(result) == [SetUpProblemCode.NOT_A_MEMBER]


def test_a_member_whose_cf_project_is_gone_is_removed_by_its_id(store: Store) -> None:
    with store.write() as transaction:
        insert_member(
            transaction,
            project_id="deleted-in-cf",
            program_id="demo",
            rules_paths=(),
            authorize_allow=(),
            authorize_deny=(),
            registered_at=NOW,
            updated_at=NOW,
        )

    result = _set_up(
        store, {"program": "demo", "remove": {"members": ["deleted-in-cf"]}}
    )

    assert result.changes == ("removed member deleted-in-cf",)


def test_the_concept_member_cannot_go_while_the_concept_stays(store: Store) -> None:
    _set_up(store, _program(concept=CONCEPT))

    result = _set_up(store, REMOVE_CONSUMER)

    assert _codes(result) == [SetUpProblemCode.CONCEPT_MEMBER_NOT_MEMBER]
    assert "concept: null" in result.problems[0].detail
    assert _removed_at(store, "consumer-id") is None


def test_clearing_the_concept_in_the_same_request_removes_both(store: Store) -> None:
    _set_up(store, _program(concept=CONCEPT))

    result = _set_up(store, {**REMOVE_CONSUMER, "concept": None})

    assert result.outcome is SetUpOutcome.APPLIED
    assert "removed member consumer-id" in result.changes
    assert result.program is not None
    assert result.program.concept is None
    with store.read() as transaction:
        program = get_program(transaction, "demo")
    assert program is not None
    assert program.concept_member is None


def test_moving_the_concept_in_the_same_request_allows_the_removal(
    store: Store,
) -> None:
    _set_up(store, _program(concept=CONCEPT))

    result = _set_up(
        store,
        {
            **REMOVE_CONSUMER,
            "concept": {"member": "provider", "path": "docs/concept.md"},
        },
    )

    assert result.outcome is SetUpOutcome.APPLIED
    assert result.program is not None
    assert result.program.concept is not None
    assert result.program.concept.member == "provider-id"


def test_one_blocked_removal_rejects_the_whole_request(store: Store) -> None:
    _open_question(store, CLAIMED, waiting=False)

    result = _set_up(
        store,
        {"program": "demo", "remove": {"members": ["provider", "consumer"]}},
    )

    assert _codes(result) == [SetUpProblemCode.MEMBER_HAS_OPEN_QUESTIONS]
    assert result.changes == ()
    assert _removed_at(store, "provider-id") is None
    assert _removed_at(store, "consumer-id") is None
    with store.read() as transaction:
        assert get_pair(transaction, "provider-id", "consumer-id") is not None
