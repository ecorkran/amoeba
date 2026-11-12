"""``resolve_member``: a directory to its program member, via recorded CF output."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from cf_fixtures import (
    DEFAULT_WORKTREE,
    NON_DEFAULT_WORKTREE,
    OUTSIDE_ANY_PROJECT,
    SUBDIRECTORY,
    fake_cf_run,
    fixture_document,
)

from amoeba.operations.members import (
    ContextForgeError,
    NotAProject,
    NotInProgram,
    resolve_member,
)
from amoeba.store.models import Member, MemberSettings
from amoeba.store.programs import remove_member, upsert_member, upsert_program
from amoeba.store.store import Store

NOW = datetime(2026, 11, 9, 12, 0, tzinfo=UTC)
DIRECTORY = Path("/work/checkout")
FIXTURE_PROJECT_ID: str = fixture_document(DEFAULT_WORKTREE)["id"]


def _register(store: Store, project_id: str) -> None:
    with store.write() as transaction:
        upsert_program(
            transaction,
            program_id="demo",
            concept_member=None,
            concept_path=None,
            now=NOW,
        )
        upsert_member(
            transaction,
            program_id="demo",
            settings=MemberSettings(
                project_id=project_id,
                rules_paths=("CLAUDE.md",),
                authorize_allow=(),
                authorize_deny=(),
            ),
            now=NOW,
        )


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    with Store.open(tmp_path / "amoeba.sqlite3") as opened:
        yield opened


@pytest.mark.parametrize(
    "fixture", [DEFAULT_WORKTREE, NON_DEFAULT_WORKTREE, SUBDIRECTORY]
)
def test_every_view_of_a_repo_gives_the_same_member(store: Store, fixture: str) -> None:
    _register(store, FIXTURE_PROJECT_ID)

    result = resolve_member(store, DIRECTORY, fake_cf_run(fixture))

    assert isinstance(result, Member)
    assert result.project_id == FIXTURE_PROJECT_ID
    assert result.program_id == "demo"


def test_a_cf_project_outside_the_program_is_not_in_program(store: Store) -> None:
    _register(store, "some-other-project")

    result = resolve_member(store, DIRECTORY, fake_cf_run(DEFAULT_WORKTREE))

    assert result == NotInProgram(FIXTURE_PROJECT_ID)


def test_a_removed_member_is_not_in_the_program(store: Store) -> None:
    _register(store, FIXTURE_PROJECT_ID)
    with store.write() as transaction:
        remove_member(transaction, FIXTURE_PROJECT_ID, NOW)

    result = resolve_member(store, DIRECTORY, fake_cf_run(DEFAULT_WORKTREE))

    assert result == NotInProgram(FIXTURE_PROJECT_ID)


def test_outside_any_project_is_not_a_project(store: Store) -> None:
    result = resolve_member(store, DIRECTORY, fake_cf_run(OUTSIDE_ANY_PROJECT))

    assert result == NotAProject(fixture_document(OUTSIDE_ANY_PROJECT)["message"])


def test_a_failing_cf_raises_context_forge_error(store: Store) -> None:
    with pytest.raises(ContextForgeError, match="exited 1"):
        resolve_member(store, DIRECTORY, fake_cf_run(None))
