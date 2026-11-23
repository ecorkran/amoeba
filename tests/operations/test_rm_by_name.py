"""``rm`` by name from anywhere, by caller, and ``--checkout`` (slice 261, D8)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from cf_fixtures import OUTSIDE_ANY_PROJECT, fake_cf_run
from store.question_support import claimed_question
from store.seed import insert_checkout
from store_open import open_local_store
from user_configs import user_config

from amoeba.operations.set_up_models import (
    SetUpOutcome,
    SetUpProblemCode,
    SetUpResult,
)
from amoeba.store.checkouts import checkouts_of_member, checkouts_on_machine
from amoeba.store.machines import acting_machine_id
from amoeba.store.models import QuestionKey
from amoeba.store.questions import insert_question
from amoeba.store.store import Store
from operations.rm_placed import rm
from operations.set_up_support import (
    DIRECTORY,
    RECORDED_NAME,
    FakeCf,
    run_set_up,
    seed_member,
)

NOW = __import__("datetime").datetime(
    2026, 11, 9, 12, 0, tzinfo=__import__("datetime").UTC
)
EVERYWHERE = FakeCf(directory_fixture=OUTSIDE_ANY_PROJECT)


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    with open_local_store(tmp_path / "amoeba.sqlite3") as opened:
        seed_member(opened, "demo", "forge-id", "forge")
        yield opened


def _rm(store: Store, document: dict[str, Any], cf: Any = EVERYWHERE) -> SetUpResult:
    return rm(store, user_config(), document, directory=DIRECTORY, run=cf)


def test_rm_by_name_from_a_non_project_runs_no_cf_and_reports_no_directory(
    store: Store,
) -> None:
    calls: list[object] = []

    def cf(argv: Any, **_kwargs: object) -> Any:
        calls.append(argv)
        return fake_cf_run(None)(argv)

    result = _rm(store, {"members": ["forge"]}, cf)

    assert result.outcome is SetUpOutcome.APPLIED
    assert result.changes == ("removed member forge",)
    assert result.working_directory is None
    assert calls == []


def test_rm_removes_a_member_with_no_checkout_and_cancels_its_requests(
    store: Store,
) -> None:
    with store.write() as transaction:
        transaction.execute("DELETE FROM checkouts")

    result = _rm(store, {"members": ["forge"]})

    assert result.outcome is SetUpOutcome.APPLIED


def test_a_members_checkouts_on_every_machine_go_with_it(store: Store) -> None:
    _rm(store, {"members": ["forge-id"]})

    with store.read() as transaction:
        assert checkouts_of_member(transaction, "forge-id") == ()


def test_rm_by_id_twice_is_unchanged_and_by_name_twice_is_not_a_member(
    store: Store,
) -> None:
    _rm(store, {"members": ["forge-id"]})

    by_id = _rm(store, {"members": ["forge-id"]})
    by_name = _rm(store, {"members": ["forge"]})

    assert by_id.outcome is SetUpOutcome.UNCHANGED
    assert [p.code for p in by_name.problems] == [SetUpProblemCode.NOT_A_MEMBER]


def test_a_bare_rm_removes_the_callers_member(store: Store) -> None:
    document: dict[str, Any] = {"program": "demo", "members": [{}]}
    run_set_up(store, document)

    result = _rm(store, {}, FakeCf(directory_fixture="default_worktree"))

    assert result.changes == (f"removed member {RECORDED_NAME}",)


def test_open_questions_still_refuse_a_removal(store: Store) -> None:
    with store.write() as transaction:
        insert_question(
            transaction,
            claimed_question(
                QuestionKey("run-1", "2026-11-09T11:00:00+00:00"),
                member_id="forge-id",
            ),
            now=NOW,
        )

    result = _rm(store, {"members": ["forge"]})

    assert [p.code for p in result.problems] == [
        SetUpProblemCode.MEMBER_HAS_OPEN_QUESTIONS
    ]


@pytest.mark.parametrize("suffix", ["", "/"])
def test_checkout_removes_it_and_leaves_the_member_with_or_without_a_slash(
    store: Store, suffix: str
) -> None:
    result = _rm(store, {"checkout": f"/work/forge{suffix}"})

    assert result.outcome is SetUpOutcome.APPLIED
    assert result.changes == ("removed checkout /work/forge" + suffix,)
    with store.read() as transaction:
        assert checkouts_of_member(transaction, "forge-id") == ()
        assert (
            transaction.execute(
                "SELECT removed_at FROM members WHERE project_id = 'forge-id'"
            ).fetchone()[0]
            is None
        )


def test_two_rows_at_one_path_both_go(store: Store) -> None:
    with store.write() as transaction:
        insert_checkout(
            transaction,
            member_id="forge-id",
            cf_project_id="cf-second",
            path="/work/forge",
            now=NOW,
        )

    _rm(store, {"checkout": "/work/forge"})

    with store.read() as transaction:
        assert checkouts_on_machine(transaction, acting_machine_id(transaction)) == ()


def test_an_unknown_checkout_is_not_a_checkout_listing_the_stored_paths(
    store: Store,
) -> None:
    result = _rm(store, {"checkout": "/nowhere"})

    assert [p.code for p in result.problems] == [SetUpProblemCode.NOT_A_CHECKOUT]
    assert "/work/forge" in result.problems[0].detail


@pytest.mark.parametrize(
    "document",
    [
        {"checkout": "relative/path"},
        {"checkout": "/work/forge", "members": ["forge"]},
        {"checkout": "/work/forge", "pairs": ["a:b"]},
        {"checkout": "/work/forge", "concept": True},
    ],
)
def test_a_relative_or_combined_checkout_is_malformed(
    store: Store, document: dict[str, Any]
) -> None:
    result = _rm(store, document)

    assert [p.code for p in result.problems] == [SetUpProblemCode.MALFORMED]
    with store.read() as transaction:
        assert len(checkouts_of_member(transaction, "forge-id")) == 1


def test_the_last_checkout_leaves_a_member_with_none(store: Store) -> None:
    _rm(store, {"checkout": "/work/forge"})

    with store.read() as transaction:
        assert checkouts_of_member(transaction, "forge-id") == ()
