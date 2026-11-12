"""Moving the legacy directories and handling two stores (slice 228, D2 step 5)."""

from __future__ import annotations

import shutil
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from amoeba.operations.state_move import prepare_state_home
from amoeba.operations.state_move_types import MoveHooks, MoveStep
from amoeba.store.relocate import copy_store
from operations.state_move_support import (
    ANSWERING_SCRATCH,
    SELECT_ANSWERS,
    Crash,
    legacy_leftovers,
    make_layout,
    rows,
    seed_legacy_home,
)

MOVED_FILES = (
    f"answering/{ANSWERING_SCRATCH}/prompt.txt",
    f"logs/answering/{ANSWERING_SCRATCH}.stdout.log",
    "logs/resume/run-a/1.log",
)
INSERT_LATE_ANSWER = (
    "INSERT INTO answers (run_id, paused_at, answered_by, answer, recorded_at)"
    " VALUES ('run-c', '2026-11-01T11:00:00Z', 'answerer', 'late',"
    " '2026-11-02T00:00:00Z')"
)


def _crash_on_first_directory(step: MoveStep) -> None:
    if step is MoveStep.DIRECTORY_MOVED:
        raise Crash(step.value)


def test_a_fresh_move_leaves_only_the_config_and_a_second_call_says_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    layout = make_layout(tmp_path)
    seed_legacy_home(layout)

    first = prepare_state_home(layout)
    first_stderr = capsys.readouterr().err
    second = prepare_state_home(layout)

    assert first.store_moved
    assert first.entries_moved == 3
    assert legacy_leftovers(layout) == ["config.yaml"]
    for relative in MOVED_FILES:
        assert (layout.state_home / relative).is_file()
    assert first_stderr.count("moved state from") == 1
    assert not second.moved_anything
    assert capsys.readouterr().err == ""


def test_a_crash_after_the_first_entry_then_a_clean_rerun_ends_complete(
    tmp_path: Path,
) -> None:
    layout = make_layout(tmp_path)
    legacy_store = seed_legacy_home(layout)

    with pytest.raises(Crash):
        prepare_state_home(
            layout, hooks=MoveHooks(after_step=_crash_on_first_directory)
        )
    # The legacy store went before the crash: nothing may bring it back.
    assert not legacy_store.exists()
    prepare_state_home(layout)

    assert not legacy_store.exists()
    assert legacy_leftovers(layout) == ["config.yaml"]
    for relative in MOVED_FILES:
        assert (layout.state_home / relative).is_file()


def test_a_stale_moving_entry_is_removed_and_the_entry_moved_again(
    tmp_path: Path,
) -> None:
    layout = make_layout(tmp_path)
    seed_legacy_home(layout)
    stale = layout.state_home / "answering" / f".{ANSWERING_SCRATCH}.moving"
    stale.mkdir(parents=True)
    (stale / "half-copied.txt").write_text("partial", encoding="utf-8")

    prepare_state_home(layout)

    assert not stale.exists()
    assert (
        layout.state_home / "answering" / ANSWERING_SCRATCH / "prompt.txt"
    ).is_file()
    assert legacy_leftovers(layout) == ["config.yaml"]


def test_a_mover_that_copies_then_deletes_works_across_filesystems(
    tmp_path: Path,
) -> None:
    layout = make_layout(tmp_path)
    seed_legacy_home(layout)

    def copy_then_delete(source: Path, destination: Path) -> None:
        if source.is_dir():
            shutil.copytree(source, destination)
            shutil.rmtree(source)
        else:
            shutil.copy2(source, destination)
            source.unlink()

    prepare_state_home(layout, hooks=MoveHooks(move_directory=copy_then_delete))

    assert legacy_leftovers(layout) == ["config.yaml"]
    for relative in MOVED_FILES:
        assert (layout.state_home / relative).is_file()


def _place_identical_copy(layout_legacy: Path, state_store: Path, state: Path) -> None:
    state.mkdir(parents=True, exist_ok=True)
    copy_store(layout_legacy, state_store, str(layout_legacy.parent), str(state))


def test_identical_double_stores_delete_the_legacy_one(tmp_path: Path) -> None:
    layout = make_layout(tmp_path)
    legacy_store = seed_legacy_home(layout)
    _place_identical_copy(legacy_store, layout.store_path, layout.state_home)

    report = prepare_state_home(layout)

    assert not report.store_moved
    assert not legacy_store.exists()
    assert not list(layout.state_home.glob("*.legacy-*"))
    assert legacy_leftovers(layout) == ["config.yaml"]


def test_differing_double_stores_keep_the_state_store_and_set_the_legacy_aside(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    layout = make_layout(tmp_path)
    legacy_store = seed_legacy_home(layout)
    _place_identical_copy(legacy_store, layout.store_path, layout.state_home)
    state_before = rows(layout.store_path, SELECT_ANSWERS)
    with closing(sqlite3.connect(legacy_store)) as connection:
        connection.execute(INSERT_LATE_ANSWER)  # an old install kept writing
        connection.commit()

    prepare_state_home(layout)

    assert rows(layout.store_path, SELECT_ANSWERS) == state_before
    assert not legacy_store.exists()
    (aside,) = (
        path
        for path in layout.state_home.glob("amoeba.sqlite3.legacy-*")
        if not path.name.endswith(("-wal", "-shm"))
    )
    assert len(rows(aside, SELECT_ANSWERS)) == len(state_before) + 1
    stderr = capsys.readouterr().err
    assert str(aside) in stderr
    assert "answers=4" in stderr
    assert "answers=3" in stderr
    assert "MAX(answers.seq)=4" in stderr
    assert legacy_leftovers(layout) == ["config.yaml"]
    assert (layout.legacy_home or tmp_path).joinpath("config.yaml").read_text(
        encoding="utf-8"
    ) == "answer_limit: 3\n"


def test_stores_with_equal_counts_but_an_edited_row_are_not_the_same(
    tmp_path: Path,
) -> None:
    layout = make_layout(tmp_path)
    legacy_store = seed_legacy_home(layout)
    _place_identical_copy(legacy_store, layout.store_path, layout.state_home)
    with closing(sqlite3.connect(legacy_store)) as connection:
        connection.execute("UPDATE answers SET answer = 'edited in place'")
        connection.commit()

    prepare_state_home(layout)

    (aside,) = (
        path
        for path in layout.state_home.glob("amoeba.sqlite3.legacy-*")
        if not path.name.endswith(("-wal", "-shm"))
    )
    assert {row[0] for row in rows(aside, "SELECT answer FROM answers")} == {
        "edited in place"
    }
