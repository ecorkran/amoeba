"""The interim name and checkout ``set_up`` writes until ``add`` is rewritten
(slice 261, 1.1 and 2.3)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from store_open import open_local_store

from amoeba.operations.set_up_models import SetUpOutcome
from amoeba.store.checkouts import checkouts_of_member
from amoeba.store.programs import get_member, get_member_any
from amoeba.store.store import Store
from operations.set_up_support import RECORDED_ID, RECORDED_NAME, run_set_up

#: The working directory's project joins the program ``demo``.
WORKING: dict[str, Any] = {"program": "demo", "members": [{}]}


def _with_project(project: str) -> dict[str, Any]:
    return {"program": "demo", "members": [{"project": project}]}


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    with open_local_store(tmp_path / "amoeba.sqlite3") as opened:
        yield opened


def _name_of(store: Store, project_id: str) -> str:
    with store.read() as transaction:
        member = get_member_any(transaction, project_id)
    assert member is not None
    return member.name


def test_a_new_member_is_named_for_its_context_forge_project_with_one_checkout(
    store: Store,
) -> None:
    run_set_up(store, WORKING)
    run_set_up(store, WORKING)

    with store.read() as transaction:
        checkouts = checkouts_of_member(transaction, RECORDED_ID)
    assert _name_of(store, RECORDED_ID) == RECORDED_NAME
    assert [c.cf_project_id for c in checkouts] == [RECORDED_ID]


@pytest.mark.parametrize("taken", [RECORDED_NAME, RECORDED_NAME.upper()])
def test_a_second_project_with_a_taken_name_is_named_by_its_id(
    store: Store, taken: str
) -> None:
    run_set_up(store, WORKING)

    result = run_set_up(
        store,
        _with_project("other-id"),
        projects=[("other-id", taken)],
    )

    assert result.outcome is SetUpOutcome.APPLIED
    assert _name_of(store, "other-id") == "other-id"


def test_a_name_with_a_space_is_replaced_by_the_id(store: Store) -> None:
    result = run_set_up(
        store,
        _with_project("spaced-id"),
        projects=[("spaced-id", "has a space")],
    )

    assert result.outcome is SetUpOutcome.APPLIED
    assert _name_of(store, "spaced-id") == "spaced-id"


def test_a_removed_member_comes_back_by_its_id_when_its_name_was_taken(
    store: Store,
) -> None:
    run_set_up(store, WORKING)
    run_set_up(store, {"program": "demo", "remove": {"members": [RECORDED_ID]}})
    run_set_up(
        store,
        _with_project("other-id"),
        projects=[("other-id", RECORDED_NAME)],
    )
    assert _name_of(store, "other-id") == RECORDED_NAME

    result = run_set_up(store, WORKING, projects=[("other-id", RECORDED_NAME)])

    assert result.outcome is SetUpOutcome.APPLIED
    assert _name_of(store, RECORDED_ID) == RECORDED_ID
    with store.read() as transaction:
        assert get_member(transaction, RECORDED_ID) is not None
