"""read_member: one test per reason, precedence, and no escaping exception.

Stores, links and snapshots are written by the tests; no live CF or ``sq``.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from program_harness import (
    CF_PROJECT_ID,
    a_member,
    link_member_store,
    observe,
    open_member_store,
)

from amoeba.program import (
    MemberUnreadableReason,
    Readable,
    Unreadable,
    read_member,
)
from amoeba.store import sql
from amoeba.store.paths import project_store_path
from amoeba.upstream.context_forge import (
    FIELD_INDEX_RANGE,
    FIELD_WORKTREE_PATH,
    Checkout,
)

PROJECT = "data"
SHORT_TIMEOUT_SECONDS = 0.1


@pytest.fixture
def supervisor_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "supervisor"
    directory.mkdir()
    return directory


@pytest.fixture
def checkout_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "checkout"
    directory.mkdir()
    return directory


def _unreadable(supervisor_dir: Path, project: str = PROJECT) -> Unreadable:
    state = read_member(supervisor_dir, a_member(project))
    assert isinstance(state, Unreadable), state
    return state


def _linked_store(supervisor_dir: Path, project: str = PROJECT) -> None:
    with open_member_store(supervisor_dir, project) as store:
        link_member_store(store, project, CF_PROJECT_ID)


def test_store_missing_names_the_expected_file(supervisor_dir: Path) -> None:
    state = _unreadable(supervisor_dir)

    assert state.reason is MemberUnreadableReason.STORE_MISSING
    assert f"{PROJECT}.sqlite3" in state.detail


def test_store_unreadable_for_a_corrupt_file(supervisor_dir: Path) -> None:
    project_store_path(supervisor_dir, PROJECT).write_bytes(b"junk" * 100)

    state = _unreadable(supervisor_dir)

    assert state.reason is MemberUnreadableReason.STORE_UNREADABLE
    assert state.detail


def test_store_unreadable_for_a_wrong_schema_version(supervisor_dir: Path) -> None:
    open_member_store(supervisor_dir, PROJECT).close()
    with sqlite3.connect(project_store_path(supervisor_dir, PROJECT)) as connection:
        connection.execute(sql.UPSERT_SCHEMA_VERSION, (sql.SCHEMA_META_ROW_ID, 999))

    state = _unreadable(supervisor_dir)

    assert state.reason is MemberUnreadableReason.STORE_UNREADABLE
    assert "999" in state.detail


def test_store_unreadable_for_a_lock_held_past_a_short_timeout(
    supervisor_dir: Path,
) -> None:
    open_member_store(supervisor_dir, PROJECT).close()
    blocker = sqlite3.connect(project_store_path(supervisor_dir, PROJECT))
    blocker.execute("PRAGMA locking_mode=EXCLUSIVE")
    blocker.execute("SELECT count(*) FROM nodes").fetchall()
    blocker.execute("BEGIN EXCLUSIVE")
    try:
        state = read_member(
            supervisor_dir,
            a_member(PROJECT),
            busy_timeout_seconds=SHORT_TIMEOUT_SECONDS,
        )
    finally:
        blocker.rollback()
        blocker.close()

    assert isinstance(state, Unreadable)
    assert state.reason is MemberUnreadableReason.STORE_UNREADABLE
    assert "locked" in state.detail


def test_unlinked_with_no_link(supervisor_dir: Path) -> None:
    open_member_store(supervisor_dir, PROJECT).close()

    state = _unreadable(supervisor_dir)

    assert state.reason is MemberUnreadableReason.UNLINKED
    assert "no CF link" in state.detail


def test_unlinked_with_two_links_chooses_none(supervisor_dir: Path) -> None:
    with open_member_store(supervisor_dir, PROJECT) as store:
        link_member_store(store, PROJECT, "cf-one")
        link_member_store(store, PROJECT, "cf-two")

    state = _unreadable(supervisor_dir)

    assert state.reason is MemberUnreadableReason.UNLINKED
    assert "2 CF links" in state.detail


def test_snapshot_missing_names_the_cf_project(supervisor_dir: Path) -> None:
    _linked_store(supervisor_dir)

    state = _unreadable(supervisor_dir)

    assert state.reason is MemberUnreadableReason.SNAPSHOT_MISSING
    assert CF_PROJECT_ID in state.detail


def test_checkout_unresolved_carries_the_resolver_reason(
    supervisor_dir: Path, tmp_path: Path
) -> None:
    gone = tmp_path / "no-such-checkout"
    with open_member_store(supervisor_dir, PROJECT) as store:
        link_member_store(store, PROJECT, CF_PROJECT_ID)
        observe(store, PROJECT, CF_PROJECT_ID, project_path=gone)

    state = _unreadable(supervisor_dir)

    assert state.reason is MemberUnreadableReason.CHECKOUT_UNRESOLVED
    assert "not an existing directory" in state.detail


def test_readable_with_no_worktrees_uses_the_project_path(
    supervisor_dir: Path, checkout_dir: Path
) -> None:
    with open_member_store(supervisor_dir, PROJECT) as store:
        link_member_store(store, PROJECT, CF_PROJECT_ID)
        observe(store, PROJECT, CF_PROJECT_ID, project_path=checkout_dir)

    state = read_member(supervisor_dir, a_member(PROJECT))

    assert state == Readable(
        cf_project_id=CF_PROJECT_ID, checkout=Checkout(checkout_dir, None)
    )


def test_readable_when_a_worktree_owns_the_members_index(
    supervisor_dir: Path, checkout_dir: Path, tmp_path: Path
) -> None:
    other = tmp_path / "other"
    other.mkdir()
    worktrees: dict[str, object] = {
        "wt_a": {FIELD_WORKTREE_PATH: str(other), FIELD_INDEX_RANGE: [100, 199]},
        "wt_b": {FIELD_WORKTREE_PATH: str(checkout_dir), FIELD_INDEX_RANGE: [700, 799]},
    }
    with open_member_store(supervisor_dir, PROJECT) as store:
        link_member_store(store, PROJECT, CF_PROJECT_ID)
        observe(
            store,
            PROJECT,
            CF_PROJECT_ID,
            project_path=other,
            worktrees=worktrees,
        )

    state = read_member(supervisor_dir, a_member(PROJECT, initiative=790))

    assert state == Readable(
        cf_project_id=CF_PROJECT_ID, checkout=Checkout(checkout_dir, "wt_b")
    )


def test_a_member_failing_two_checks_reports_the_earlier(
    supervisor_dir: Path,
) -> None:
    """Corrupt *and* unlinked: the store failure comes first."""
    project_store_path(supervisor_dir, PROJECT).write_bytes(b"junk" * 100)

    assert _unreadable(supervisor_dir).reason is MemberUnreadableReason.STORE_UNREADABLE

    # Linked but with no snapshot, and the checkout would also be unresolved.
    _linked_store(supervisor_dir, "other")
    assert (
        _unreadable(supervisor_dir, "other").reason
        is MemberUnreadableReason.SNAPSHOT_MISSING
    )


def test_the_members_store_file_is_unchanged_by_the_call(
    supervisor_dir: Path,
) -> None:
    _linked_store(supervisor_dir)
    path = project_store_path(supervisor_dir, PROJECT)
    before = path.read_bytes()

    read_member(supervisor_dir, a_member(PROJECT))

    assert path.read_bytes() == before
