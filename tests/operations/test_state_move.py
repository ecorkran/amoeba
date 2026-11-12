"""Moving the legacy store to the state home (slice 228, D2 steps 1 to 4)."""

from __future__ import annotations

import sqlite3
import threading
from collections.abc import Callable
from contextlib import closing
from pathlib import Path

import pytest

from amoeba.operations import state_move, state_move_store
from amoeba.operations.state_move import prepare_state_home
from amoeba.operations.state_move_types import MoveHooks, MoveStep
from amoeba.store.errors import StoreBusyError, StoreRelocateError
from amoeba.store.relocate import copy_store
from amoeba.store.store import Store
from operations.state_move_support import (
    SELECT_ANSWERS,
    Crash,
    crash_after,
    legacy_leftovers,
    make_layout,
    rows,
    seed_legacy_home,
)

STORE_STEPS = (
    MoveStep.OPENED,
    MoveStep.LOCKED,
    MoveStep.BACKED_UP,
    MoveStep.VERIFIED,
    MoveStep.PLACED,
    MoveStep.LEGACY_DELETED,
)
SHORT_BUSY_TIMEOUT_SECONDS = 0.2
LOCK_HELD_SECONDS = 0.5
LONG_BUSY_TIMEOUT_SECONDS = 10.0


def test_a_legacy_store_moves_with_every_row_and_resume_log(tmp_path: Path) -> None:
    layout = make_layout(tmp_path)
    legacy_store = seed_legacy_home(layout)
    before = rows(legacy_store, SELECT_ANSWERS)

    report = prepare_state_home(layout)

    assert report.store_moved
    assert not legacy_store.exists()
    after = rows(layout.store_path, SELECT_ANSWERS)
    assert [row[:2] for row in after] == [row[:2] for row in before]
    assert after[0][2] == f"{layout.state_home}/logs/resume/run-a/1.log"
    assert after[1][2] == "/elsewhere/logs/run-b.log"
    assert after[2][2] is None
    with Store.open(layout.store_path):
        pass


@pytest.mark.parametrize("step", STORE_STEPS, ids=lambda step: step.value)
def test_a_crash_after_each_step_is_followed_by_a_clean_rerun(
    tmp_path: Path, step: MoveStep
) -> None:
    layout = make_layout(tmp_path)
    legacy_store = seed_legacy_home(layout)
    expected = [row[:2] for row in rows(legacy_store, SELECT_ANSWERS)]

    with pytest.raises(Crash):
        prepare_state_home(layout, hooks=MoveHooks(after_step=crash_after(step)))
    prepare_state_home(layout)

    assert [row[:2] for row in rows(layout.store_path, SELECT_ANSWERS)] == expected
    assert not legacy_store.exists()
    assert legacy_leftovers(layout) == ["config.yaml"]
    assert not list(layout.state_home.glob("*.moving"))
    assert not list(layout.state_home.glob("*.legacy-*"))


def test_a_legacy_file_deleted_by_a_racing_process_counts_as_already_moved(
    tmp_path: Path,
) -> None:
    layout = make_layout(tmp_path)
    legacy_store = seed_legacy_home(layout)

    def racing_process_finishes(step: MoveStep) -> None:
        if step is MoveStep.OPENED:
            legacy_store.unlink()

    report = prepare_state_home(
        layout, hooks=MoveHooks(after_step=racing_process_finishes)
    )

    assert not report.store_moved
    assert not list(legacy_store.parent.glob("amoeba.sqlite3*"))
    assert not layout.store_path.exists()
    assert report.entries_moved == 3  # step 5 still ran


def test_a_copy_error_leaves_the_legacy_store_untouched_and_the_next_call_moves_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    layout = make_layout(tmp_path)
    legacy_store = seed_legacy_home(layout)
    before = rows(legacy_store, SELECT_ANSWERS)

    def failing_copy(
        old: Path,
        new: Path,
        old_prefix: str,
        new_prefix: str,
        *,
        after_backup: Callable[[], None] | None = None,
    ) -> None:
        def fail() -> None:
            raise OSError("disk full")

        copy_store(old, new, old_prefix, new_prefix, after_backup=fail)

    monkeypatch.setattr(state_move_store, "copy_store", failing_copy)
    with pytest.raises(StoreRelocateError, match="disk full"):
        prepare_state_home(layout)
    monkeypatch.undo()

    assert rows(legacy_store, SELECT_ANSWERS) == before
    assert not layout.store_path.exists()
    assert not list(layout.state_home.glob("*.moving*"))

    assert prepare_state_home(layout).store_moved
    assert not legacy_store.exists()


def test_an_os_error_anywhere_in_the_move_is_a_relocate_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    layout = make_layout(tmp_path)
    seed_legacy_home(layout)

    def failing_move(*arguments: object) -> bool:
        raise PermissionError("not allowed")

    monkeypatch.setattr(state_move, "move_store", failing_move)

    with pytest.raises(StoreRelocateError, match="not allowed"):
        prepare_state_home(layout)


def _hold_legacy_lock(legacy_store: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(
        legacy_store, isolation_level=None, check_same_thread=False
    )
    connection.execute("BEGIN IMMEDIATE")
    return connection


def test_a_held_legacy_lock_past_the_timeout_raises_busy_with_nothing_written(
    tmp_path: Path,
) -> None:
    layout = make_layout(tmp_path)
    legacy_store = seed_legacy_home(layout)
    holder = _hold_legacy_lock(legacy_store)
    try:
        with pytest.raises(StoreBusyError):
            prepare_state_home(layout, busy_timeout_seconds=SHORT_BUSY_TIMEOUT_SECONDS)
    finally:
        holder.close()

    assert not layout.store_path.exists()
    assert not list(layout.state_home.glob("*.moving*"))
    assert legacy_store.exists()


def test_a_held_legacy_lock_delays_the_move_until_released(tmp_path: Path) -> None:
    layout = make_layout(tmp_path)
    legacy_store = seed_legacy_home(layout)
    holder = _hold_legacy_lock(legacy_store)
    release = threading.Timer(LOCK_HELD_SECONDS, holder.rollback)
    release.start()
    try:
        report = prepare_state_home(
            layout, busy_timeout_seconds=LONG_BUSY_TIMEOUT_SECONDS
        )
    finally:
        release.join()
        holder.close()

    assert report.store_moved
    assert not legacy_store.exists()
    with closing(sqlite3.connect(layout.store_path)) as connection:
        assert connection.execute("SELECT COUNT(*) FROM answers").fetchone() == (3,)
