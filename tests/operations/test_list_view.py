"""``list``'s default view and ``--all`` (slice 229, D3, tasks 7.3 and 7.4)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path

import pytest
from store.decision_support import CORE, LINT, TOOLS, TRADING, seed_programs
from store.question_support import NOW, claimed_question
from user_configs import user_config

from amoeba.answering.values import AnsweredBy
from amoeba.operations.deps import Deps
from amoeba.operations.list_registry import ProgramsView
from amoeba.operations.list_view import (
    SUBJECT_ALIASES,
    ListOutcome,
    ListRequest,
    ListResult,
    ListSubject,
    list_view,
)
from amoeba.operations.reject_codes import RejectCode
from amoeba.operations.status import status
from amoeba.operations.status_models import StatusOutcome
from amoeba.store.answers import add_pm_answer, record_resume
from amoeba.store.models import QuestionKey
from amoeba.store.question_closing import close_question
from amoeba.store.questions import get_question, insert_question
from amoeba.store.store import Store
from amoeba.store.vocabulary import ClosedReason, ResumeOutcome
from operations.list_support import ListCf, names_of, project_entry
from operations.status_support import CfAnswer, status_deps

ELSEWHERE = Path("/work/elsewhere")
PROJECTS = [project_entry(CORE, "core", "/work/core"), project_entry(LINT, "lint")]
CONFIG = user_config()
RECENT = QuestionKey("run-recent", "2026-11-09T10:00:00+00:00")
OLD = QuestionKey("run-old", "2026-09-01T10:00:00+00:00")
ANSWERED = QuestionKey("run-answered", "2026-11-09T11:00:00+00:00")


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    with Store.open(tmp_path / "amoeba.sqlite3") as opened:
        seed_programs(opened)
        yield opened


def _deps(tmp_path: Path) -> Deps:
    cf = ListCf(PROJECTS, {ELSEWHERE: CfAnswer.NOT_A_PROJECT})
    return status_deps(tmp_path, cf=cf, runs=[], names=names_of(PROJECTS))


def _list(
    store: Store, tmp_path: Path, document: dict[str, object] | None = None
) -> ListOutcome:
    return list_view(
        store, CONFIG, document or {}, directory=ELSEWHERE, deps=_deps(tmp_path)
    )


def _settle_two(store: Store) -> None:
    """One question closed 2 days ago, one closed 60 days ago (window is 30)."""
    with store.write() as transaction:
        for key, member, age in ((RECENT, CORE, 2), (OLD, LINT, 60)):
            insert_question(
                transaction,
                claimed_question(key, member_id=member),
                now=NOW - timedelta(days=age + 1),
            )
            current = get_question(transaction, key)
            assert current is not None
            assert close_question(
                transaction,
                key,
                ClosedReason.DISMISSED,
                "not needed",
                current.state,
                current.updated_at,
                NOW - timedelta(days=age),
            )


def test_no_subject_gives_the_status_result_unchanged(
    store: Store, tmp_path: Path
) -> None:
    result = _list(store, tmp_path)

    expected = status(store, CONFIG, {}, directory=ELSEWHERE, deps=_deps(tmp_path))
    assert isinstance(result, ListResult)
    assert result.status == expected
    assert result.settled is None
    assert result.document() == expected.model_dump(mode="json")
    assert "settled" not in result.document()


def test_a_program_filter_reaches_status(store: Store, tmp_path: Path) -> None:
    result = _list(store, tmp_path, {"program": TRADING})

    assert isinstance(result, ListResult)
    assert [entry.program for entry in result.status.programs] == [TRADING]


def test_all_adds_settled_and_nothing_else(store: Store, tmp_path: Path) -> None:
    _settle_two(store)
    plain = _list(store, tmp_path)
    everything = _list(store, tmp_path, {"all": True})

    assert isinstance(plain, ListResult)
    assert isinstance(everything, ListResult)
    assert everything.status == plain.status
    document = everything.document()
    assert set(document) - set(plain.document()) == {"settled"}
    assert {k: v for k, v in document.items() if k != "settled"} == plain.document()


def test_settled_holds_what_ended_inside_the_window_with_names(
    store: Store, tmp_path: Path
) -> None:
    _settle_two(store)
    with store.write() as transaction:
        insert_question(
            transaction, claimed_question(ANSWERED, member_id=LINT), now=NOW
        )
        seq = add_pm_answer(transaction, ANSWERED, "yes", now=NOW, via=None)
        record_resume(
            transaction, seq, ResumeOutcome.RESUMED, detail=None, log=None, at=NOW
        )

    result = _list(store, tmp_path, {"all": True})

    assert isinstance(result, ListResult)
    assert result.settled is not None
    assert [(e.run_id, e.ended) for e in result.settled] == [
        (ANSWERED.run_id, AnsweredBy.PM),
        (RECENT.run_id, ClosedReason.DISMISSED),
    ]
    assert [e.member_name for e in result.settled] == ["lint", "core"]
    assert [e.program for e in result.settled] == [TOOLS, TRADING]


def test_a_settled_item_older_than_the_window_is_absent(
    store: Store, tmp_path: Path
) -> None:
    _settle_two(store)

    result = _list(store, tmp_path, {"all": True})

    assert isinstance(result, ListResult)
    assert result.settled is not None
    assert OLD.run_id not in [e.run_id for e in result.settled]


def test_settled_follows_the_program_filter(store: Store, tmp_path: Path) -> None:
    _settle_two(store)

    result = _list(store, tmp_path, {"all": True, "program": TOOLS})

    assert isinstance(result, ListResult)
    assert result.settled == ()


def test_settled_with_nothing_settled_is_empty_not_null(
    store: Store, tmp_path: Path
) -> None:
    result = _list(store, tmp_path, {"all": True})

    assert isinstance(result, ListResult)
    assert result.settled == ()


@pytest.mark.parametrize("subject", ["members", "dependencies", "member", "dependency"])
def test_all_with_members_or_dependencies_is_rejected(
    store: Store, tmp_path: Path, subject: str
) -> None:
    result = _list(store, tmp_path, {"subject": subject, "all": True})

    assert isinstance(result, ListResult)
    assert result.status.outcome is StatusOutcome.REJECTED
    assert result.status.rejection is RejectCode.MALFORMED
    assert "all does not apply" in result.status.problems[0]


def test_all_with_programs_is_accepted(store: Store, tmp_path: Path) -> None:
    result = _list(store, tmp_path, {"subject": "programs", "all": True})

    assert isinstance(result, ProgramsView)


def test_an_unknown_program_is_rejected_listing_the_known_ones(
    store: Store, tmp_path: Path
) -> None:
    result = _list(store, tmp_path, {"subject": "members", "program": "typo"})

    assert isinstance(result, ListResult)
    assert result.status.rejection is RejectCode.UNKNOWN_PROGRAM
    assert TRADING in result.status.problems[0]


def test_a_bad_subject_is_malformed(store: Store, tmp_path: Path) -> None:
    result = _list(store, tmp_path, {"subject": "everything"})

    assert isinstance(result, ListResult)
    assert result.status.rejection is RejectCode.MALFORMED


def test_each_singular_form_names_the_same_subject_as_its_plural() -> None:
    assert SUBJECT_ALIASES == {
        "program": ListSubject.PROGRAMS,
        "member": ListSubject.MEMBERS,
        "dependency": ListSubject.DEPENDENCIES,
    }
    for singular, subject in SUBJECT_ALIASES.items():
        assert ListRequest.model_validate({"subject": singular}).subject is subject
        assert ListRequest.model_validate({"subject": subject.value}).subject is subject
