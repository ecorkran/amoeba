"""``status`` and ``list`` name members from the store, with a ``cf`` that answers
only the caller's directory and no ``cf`` names (slice 261, D5, D13)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from store.decision_support import CORE, LINT, NAMES, seed_programs
from store_open import open_local_store
from user_configs import user_config

from amoeba.operations.list_view import ListResult
from amoeba.store.store import Store
from operations.status_placed import list_view, status
from operations.status_support import CfAnswer, FakeCf, status_deps


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    with open_local_store(tmp_path / "amoeba.sqlite3") as opened:
        seed_programs(opened)
        yield opened


def test_status_names_the_members_from_the_store(store: Store, tmp_path: Path) -> None:
    directory = tmp_path / "core"
    directory.mkdir()
    cf = FakeCf({directory: CORE})
    deps = status_deps(tmp_path, cf=cf, runs=[])

    result = status(store, user_config(), {}, directory=directory, deps=deps)

    members = {
        member.member.id: member.member.name
        for program in result.programs
        for member in program.members
    }
    assert members == {CORE: NAMES[CORE]}
    assert LINT not in members


def test_list_names_the_members_from_the_store(store: Store, tmp_path: Path) -> None:
    directory = tmp_path / "elsewhere"
    directory.mkdir()
    cf = FakeCf({directory: CfAnswer.NOT_A_PROJECT})
    deps = status_deps(tmp_path, cf=cf, runs=[])

    result = list_view(store, user_config(), {}, directory=directory, deps=deps)

    assert isinstance(result, ListResult)
    names = {
        member.member.id: member.member.name
        for program in result.status.programs
        for member in program.members
    }
    assert names == NAMES
