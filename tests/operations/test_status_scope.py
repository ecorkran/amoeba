"""``resolve_scope``: which programs ``status`` covers (slice 224, 3.4)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from store.decision_support import CORE, LINT, TOOLS, TRADING, seed_programs
from store.question_support import NOW
from store.seed import insert_program

from amoeba.operations.members import ContextForgeError
from amoeba.operations.reject_codes import RejectCode
from amoeba.operations.status import ScopedProgram, ScopeRejected, resolve_scope
from amoeba.store.store import Store
from operations.status_support import CfAnswer, FakeCf, status_deps

INSIDE_CORE = Path("/work/core")
INSIDE_LINT = Path("/work/lint")
ELSEWHERE = Path("/work/elsewhere")
UNREGISTERED = Path("/work/unregistered")


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    with Store.open(tmp_path / "amoeba.sqlite3") as opened:
        seed_programs(opened)
        with opened.write() as transaction:
            insert_program(
                transaction,
                program_id="empty",
                concept_member=None,
                concept_path=None,
                registered_at=NOW,
                updated_at=NOW,
            )
        yield opened


def _cf() -> FakeCf:
    return FakeCf(
        {
            INSIDE_CORE: CORE,
            INSIDE_LINT: LINT,
            ELSEWHERE: CfAnswer.NOT_A_PROJECT,
            UNREGISTERED: "project-not-in-any-program",
        }
    )


def _scope(
    store: Store, tmp_path: Path, directory: Path, program: str | None
) -> tuple[ScopedProgram, ...] | ScopeRejected:
    deps = status_deps(tmp_path, cf=_cf(), runs=[], names={})
    return resolve_scope(store, directory, program, deps)


def _ids(scope: tuple[ScopedProgram, ...] | ScopeRejected) -> list[str]:
    assert not isinstance(scope, ScopeRejected), scope
    return [entry.program_id for entry in scope]


def test_a_program_flag_scopes_to_that_program_from_anywhere(
    store: Store, tmp_path: Path
) -> None:
    scope = _scope(store, tmp_path, INSIDE_LINT, TRADING)

    assert _ids(scope) == [TRADING]
    assert isinstance(scope, tuple)
    assert [member.project_id for member in scope[0].members] == [CORE]


def test_inside_a_member_the_scope_is_that_members_program(
    store: Store, tmp_path: Path
) -> None:
    assert _ids(_scope(store, tmp_path, INSIDE_LINT, None)) == [TOOLS]
    assert _ids(_scope(store, tmp_path, INSIDE_CORE, None)) == [TRADING]


@pytest.mark.parametrize("directory", [ELSEWHERE, UNREGISTERED])
def test_elsewhere_the_scope_is_every_program(
    store: Store, tmp_path: Path, directory: Path
) -> None:
    assert _ids(_scope(store, tmp_path, directory, None)) == ["empty", TOOLS, TRADING]


def test_an_unknown_program_is_rejected_listing_the_known_ids(
    store: Store, tmp_path: Path
) -> None:
    scope = _scope(store, tmp_path, ELSEWHERE, "nope")

    assert isinstance(scope, ScopeRejected)
    assert scope.code is RejectCode.UNKNOWN_PROGRAM
    assert "empty, tools, trading" in scope.problems[0]


def test_a_failing_cf_while_resolving_the_directory_raises_and_never_widens(
    store: Store, tmp_path: Path
) -> None:
    deps = status_deps(
        tmp_path, cf=FakeCf({INSIDE_CORE: CfAnswer.FAILS}), runs=[], names={}
    )

    with pytest.raises(ContextForgeError):
        resolve_scope(store, INSIDE_CORE, None, deps)


def test_a_program_with_no_members_is_listed_with_no_members(
    store: Store, tmp_path: Path
) -> None:
    scope = _scope(store, tmp_path, ELSEWHERE, "empty")

    assert isinstance(scope, tuple)
    assert scope == (ScopedProgram("empty", ()),)
