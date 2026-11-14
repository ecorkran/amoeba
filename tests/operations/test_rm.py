"""``rm``: program found from the store, the engine's guards unchanged (229 D6)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from cf_fixtures import DEFAULT_WORKTREE, OUTSIDE_ANY_PROJECT, fake_cf_run
from store.question_support import NOW, claimed_question, waiting_question
from store.seed import insert_member
from user_configs import user_config

from amoeba.operations.add import add
from amoeba.operations.members import ContextForgeError
from amoeba.operations.rm import rm
from amoeba.operations.set_up_models import (
    SetUpOutcome,
    SetUpProblemCode,
    SetUpResult,
)
from amoeba.store.models import QuestionKey
from amoeba.store.programs import get_member_any, get_program
from amoeba.store.questions import insert_question
from amoeba.store.store import Store
from operations.set_up_support import (
    DIRECTORY,
    RECORDED_ID,
    FakeCf,
    row_counts,
    run_set_up,
)

PROJECTS = [
    ("provider-id", "provider"),
    ("consumer-id", "consumer"),
    ("other-id", "other-repo"),
]
RULES = {"rules_paths": ["CLAUDE.md"]}
OPEN = QuestionKey("run-open", "2026-11-10T11:00:00+00:00")
WAITING = QuestionKey("run-waiting", "2026-11-10T11:05:00+00:00")


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    """``demo`` holds the working directory's project, provider and consumer."""
    with Store.open(tmp_path / "amoeba.sqlite3") as opened:
        first = run_set_up(
            opened,
            {
                "program": "demo",
                "members": [
                    {"project": "provider", **RULES},
                    {
                        "project": "consumer",
                        **RULES,
                        "depends_on": [
                            {"provider": "provider", "consumed": "from_source"}
                        ],
                    },
                    {**RULES},
                ],
            },
            projects=PROJECTS,
        )
        second = run_set_up(
            opened,
            {"program": "second", "members": [{"project": "other-repo", **RULES}]},
            projects=PROJECTS,
        )
        assert first.outcome is second.outcome is SetUpOutcome.APPLIED
        yield opened


def _rm(
    store: Store,
    document: dict[str, Any] | None = None,
    *,
    directory_fixture: str = DEFAULT_WORKTREE,
) -> SetUpResult:
    return rm(
        store,
        user_config(),
        document or {},
        directory=DIRECTORY,
        run=FakeCf(directory_fixture=directory_fixture, projects=PROJECTS),
    )


def _codes(result: SetUpResult) -> list[SetUpProblemCode]:
    return [problem.code for problem in result.problems]


def _removed(store: Store, project_id: str) -> bool:
    with store.read() as transaction:
        member = get_member_any(transaction, project_id)
    assert member is not None
    return member.removed_at is not None


def test_no_argument_removes_the_working_directorys_member(store: Store) -> None:
    result = _rm(store)

    assert result.changes == (f"removed member {RECORDED_ID}",)
    assert _removed(store, RECORDED_ID)
    assert not _removed(store, "provider-id")


@pytest.mark.parametrize("reference", ["consumer", "consumer-id"])
def test_a_member_is_removed_by_name_or_by_id(store: Store, reference: str) -> None:
    result = _rm(store, {"members": [reference]})

    assert result.changes == ("removed member consumer-id",)


def test_an_id_works_after_the_cf_project_is_gone(store: Store) -> None:
    with store.write() as transaction:
        insert_member(
            transaction,
            project_id="gone-id",
            program_id="demo",
            rules_paths=(),
            authorize_allow=(),
            authorize_deny=(),
            registered_at=NOW,
            updated_at=NOW,
        )

    result = _rm(store, {"members": ["gone-id"]})

    assert result.changes == ("removed member gone-id",)
    assert _removed(store, "gone-id")


def test_two_members_of_one_program_are_removed_together(store: Store) -> None:
    result = _rm(store, {"members": ["provider", "consumer"]})

    assert sorted(result.changes) == [
        "removed member consumer-id",
        "removed member provider-id",
    ]


def test_members_of_two_programs_are_rejected(store: Store) -> None:
    result = _rm(store, {"members": ["provider", "other-repo"]})

    assert _codes(result) == [SetUpProblemCode.MEMBER_OF_OTHER_PROGRAM]
    assert not _removed(store, "provider-id")
    assert not _removed(store, "other-id")


def test_a_member_outside_the_named_program_is_rejected(store: Store) -> None:
    result = _rm(store, {"members": ["other-repo"], "program": "demo"})

    assert _codes(result) == [SetUpProblemCode.MEMBER_OF_OTHER_PROGRAM]
    assert "other-repo" in result.problems[0].detail


def test_a_member_in_no_program_is_not_a_member(store: Store) -> None:
    result = _rm(store, {"members": ["stranger"]})

    assert result.outcome is SetUpOutcome.REJECTED
    assert _codes(result) == [SetUpProblemCode.NOT_A_MEMBER]


def test_a_pair_is_removed_and_its_members_stay(store: Store) -> None:
    result = _rm(store, {"pairs": ["provider:consumer"]})

    assert result.changes == ("removed pair provider-id -> consumer-id",)
    assert not _removed(store, "provider-id")
    assert not _removed(store, "consumer-id")


def test_a_pair_across_programs_is_rejected(store: Store) -> None:
    result = _rm(store, {"pairs": ["provider:other-repo"]})

    assert _codes(result) == [SetUpProblemCode.MEMBER_OF_OTHER_PROGRAM]


def test_concept_clears_the_programs_concept_through_the_working_directory(
    store: Store,
) -> None:
    run_set_up(
        store,
        {
            "program": "demo",
            "concept": {"member": "consumer", "path": "docs/concept.md"},
        },
        projects=PROJECTS,
    )

    result = _rm(store, {"concept": True})

    assert result.changes == ("updated program demo",)
    with store.read() as transaction:
        program = get_program(transaction, "demo")
    assert program is not None
    assert program.concept_member is None


def test_concept_with_a_program_name_needs_no_member(store: Store) -> None:
    run_set_up(
        store,
        {"program": "demo", "concept": {"member": "consumer", "path": "docs/c.md"}},
        projects=PROJECTS,
    )

    result = _rm(
        store,
        {"concept": True, "program": "demo"},
        directory_fixture=OUTSIDE_ANY_PROJECT,
    )

    assert result.changes == ("updated program demo",)


def test_concept_for_a_program_that_does_not_exist_is_malformed_and_writes_nothing(
    store: Store,
) -> None:
    before = row_counts(store)

    result = _rm(store, {"concept": True, "program": "typo"})

    assert _codes(result) == [SetUpProblemCode.MALFORMED]
    assert row_counts(store) == before


def test_the_concepts_member_is_refused_without_concept(store: Store) -> None:
    run_set_up(
        store,
        {"program": "demo", "concept": {"member": "consumer", "path": "docs/c.md"}},
        projects=PROJECTS,
    )

    result = _rm(store, {"members": ["consumer"]})

    assert _codes(result) == [SetUpProblemCode.CONCEPT_MEMBER_NOT_MEMBER]
    assert not _removed(store, "consumer-id")


def test_open_questions_refuse_with_their_keys(store: Store) -> None:
    with store.write() as transaction:
        insert_question(
            transaction, claimed_question(OPEN, member_id="consumer-id"), now=NOW
        )
        insert_question(
            transaction, waiting_question(WAITING, member_id="consumer-id"), now=NOW
        )

    result = _rm(store, {"members": ["consumer"]})

    assert _codes(result) == [SetUpProblemCode.MEMBER_HAS_OPEN_QUESTIONS]
    assert OPEN.run_id in result.problems[0].detail
    assert WAITING.run_id in result.problems[0].detail
    assert {(q.run_id, q.paused_at) for q in result.problems[0].open_questions} == {
        (OPEN.run_id, OPEN.paused_at),
        (WAITING.run_id, WAITING.paused_at),
    }
    assert not _removed(store, "consumer-id")


def test_a_directory_outside_any_project_is_not_a_project_and_writes_nothing(
    store: Store,
) -> None:
    before = row_counts(store)

    result = _rm(store, directory_fixture=OUTSIDE_ANY_PROJECT)

    assert _codes(result) == [SetUpProblemCode.NOT_A_PROJECT]
    assert "no member was named" in result.problems[0].detail
    assert row_counts(store) == before


def test_rm_never_creates_a_program(store: Store) -> None:
    before = row_counts(store)["programs"]

    _rm(store, {"members": ["provider"]})

    assert row_counts(store)["programs"] == before


def test_cf_failing_raises_and_removes_nothing(store: Store) -> None:
    with pytest.raises(ContextForgeError):
        rm(
            store,
            user_config(),
            {"members": ["provider"]},
            directory=DIRECTORY,
            run=fake_cf_run(None),
        )

    assert not _removed(store, "provider-id")


def test_a_malformed_pair_is_malformed(store: Store) -> None:
    result = _rm(store, {"pairs": ["no-separator"]})

    assert _codes(result) == [SetUpProblemCode.MALFORMED]


def _add(store: Store, document: dict[str, Any]) -> SetUpResult:
    return add(
        store,
        user_config(),
        document,
        directory=DIRECTORY,
        run=FakeCf(directory_fixture=DEFAULT_WORKTREE, projects=PROJECTS),
    )


def test_a_removed_members_add_revives_it_in_its_old_program(store: Store) -> None:
    _rm(store, {"members": ["consumer"]})

    result = _add(store, {"project": "consumer"})

    assert result.changes == ("added member consumer-id",)
    assert result.program is not None
    assert result.program.program_id == "demo"


def test_a_removed_members_add_with_program_revives_it_in_that_one(
    store: Store,
) -> None:
    _rm(store, {"members": ["consumer"]})

    result = _add(store, {"project": "consumer", "program": "second"})

    assert result.changes == ("added member consumer-id",)
    assert result.program is not None
    assert result.program.program_id == "second"
    with store.read() as transaction:
        member = get_member_any(transaction, "consumer-id")
    assert member is not None
    assert (member.program_id, member.removed_at) == ("second", None)
