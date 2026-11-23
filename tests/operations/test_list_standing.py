"""``list standing``: the standing answers, newest first (slice 230, D4)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path

import pytest
from user_configs import user_config

from amoeba.operations.list_registry import StandingView
from amoeba.operations.list_view import ListOutcome, ListResult
from amoeba.operations.reject_codes import RejectCode
from amoeba.operations.standing import standing
from amoeba.operations.withdraw import withdraw
from amoeba.store.store import Store
from amoeba.store.vocabulary import StandingReach
from operations.list_support import ListCf, project_entry
from operations.standing_support import (
    MAX_CHARS,
    NOW,
    PROJECTS,
    seeded_store,
)
from operations.status_placed import list_view
from operations.status_support import CfAnswer, status_deps

CF_PROJECTS = [project_entry(project_id, name) for project_id, name in PROJECTS]
DIRECTORY = Path("/work/elsewhere")


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    yield from seeded_store(tmp_path / "amoeba.sqlite3")


def _give(store: Store, document: dict[str, str], minutes: int) -> int:
    given = standing(
        store,
        document,
        max_chars=MAX_CHARS,
        now=NOW + timedelta(minutes=minutes),
    )
    assert given.standing_id is not None
    return given.standing_id


def _list(
    store: Store, tmp_path: Path, document: dict[str, object], cf: ListCf | None = None
) -> ListOutcome:
    run = cf or ListCf(CF_PROJECTS, {DIRECTORY: CfAnswer.NOT_A_PROJECT})
    deps = status_deps(tmp_path, cf=run, runs=[])
    return list_view(store, user_config(), document, directory=DIRECTORY, deps=deps)


def _view(outcome: ListOutcome) -> StandingView:
    assert isinstance(outcome, StandingView)
    return outcome


def test_active_rows_newest_first_with_member_names(
    store: Store, tmp_path: Path
) -> None:
    everyone = _give(store, {"text": "all"}, 0)
    program = _give(store, {"text": "demo", "program": "demo"}, 1)
    member = _give(store, {"text": "alpha", "member": "alpha"}, 2)

    view = _view(_list(store, tmp_path, {"subject": "standing"}))

    assert [row.standing_id for row in view.standing] == [member, program, everyone]
    first = view.standing[0]
    assert (first.reach, first.member, first.member_name, first.text) == (
        StandingReach.MEMBER,
        "alpha-id",
        "alpha",
        "alpha",
    )
    assert (view.standing[1].program, view.standing[1].member_name) == ("demo", None)
    assert all(row.withdrawn_at is None for row in view.standing)


def test_all_adds_withdrawn_rows_with_date_and_reason(
    store: Store, tmp_path: Path
) -> None:
    kept = _give(store, {"text": "kept"}, 0)
    dropped = _give(store, {"text": "dropped"}, 1)
    later = NOW + timedelta(hours=1)
    withdraw(store, {"standing_id": dropped, "reason": "wrong"}, now=later)

    active = _view(_list(store, tmp_path, {"subject": "standing"}))
    every = _view(_list(store, tmp_path, {"subject": "standing", "all": True}))

    assert [row.standing_id for row in active.standing] == [kept]
    assert [row.standing_id for row in every.standing] == [dropped, kept]
    assert (every.standing[0].withdrawn_at, every.standing[0].withdraw_reason) == (
        later,
        "wrong",
    )


def test_the_default_list_has_no_standing_entries(store: Store, tmp_path: Path) -> None:
    _give(store, {"text": "all"}, 0)

    default = _list(store, tmp_path, {})

    assert isinstance(default, ListResult)
    assert "standing" not in default.document()


def test_cf_is_read_only_when_a_member_row_needs_a_name(
    store: Store, tmp_path: Path
) -> None:
    _give(store, {"text": "all"}, 0)
    cf = ListCf(CF_PROJECTS)

    _list(store, tmp_path, {"subject": "standing"}, cf)

    assert cf.listings == 0


def test_a_project_cf_no_longer_lists_has_no_name(store: Store, tmp_path: Path) -> None:
    _give(store, {"text": "alpha", "member": "alpha"}, 0)
    without_alpha = [entry for entry in CF_PROJECTS if entry["id"] != "alpha-id"]

    view = _view(_list(store, tmp_path, {"subject": "standing"}, ListCf(without_alpha)))

    assert (view.standing[0].member, view.standing[0].member_name) == (
        "alpha-id",
        None,
    )


def test_program_does_not_apply_to_standing(store: Store, tmp_path: Path) -> None:
    rejected = _list(store, tmp_path, {"subject": "standing", "program": "demo"})

    assert isinstance(rejected, ListResult)
    assert rejected.status.rejection is RejectCode.MALFORMED
    assert rejected.status.problems == ("program does not apply to standing",)
