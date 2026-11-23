"""Setting the local store aside and putting it back (slice 260, D4)."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import closing
from dataclasses import fields
from pathlib import Path

import pytest
from operations.state_move_support import make_layout, seed_legacy_home
from store_open import open_local_store
from user_configs import example_config_text

from amoeba import wiring, wiring_door
from amoeba.client.errors import HubUnreachableError
from amoeba.config.home import StateLayout, config_path
from amoeba.operations.names import Door, OperationName
from amoeba.store import migrations
from amoeba.store.errors import LocalStoreClosedError, StoreRelocateError
from amoeba.store.migrations import EXPECTED_SCHEMA_VERSION, migration_files
from amoeba.store.set_aside import (
    DISPLACED_STORES_KEPT,
    SetAsideHooks,
    set_aside_stores,
)
from amoeba.wire.join_line import JoinError
from amoeba.wiring_door import join, leave
from hub.in_process_hub import InProcessHub
from hub.join_support import (
    client_layout,
    files_of,
    line_for,
    make_local_store,
    program_ids,
)


class Stop(Exception):
    """A test's own stop, raised from a hook."""


@pytest.fixture
def hub(tmp_path: Path) -> Iterator[InProcessHub]:
    with InProcessHub(tmp_path) as running:
        yield running


def _stop() -> None:
    raise Stop


def _stopped(after: str) -> SetAsideHooks:
    return SetAsideHooks(**{after: _stop})


def _mark(store: Path) -> tuple[str, str] | None:
    with closing(sqlite3.connect(store)) as connection:
        row = connection.execute("SELECT hub_address, closed_at FROM closed_mark")
        found = row.fetchone()
    return None if found is None else (found[0], found[1])


def _left_clean(layout: StateLayout) -> None:
    """No partial copy, no side file with no store, no displaced file, one copy."""
    names = [p.name for p in layout.state_home.iterdir()]
    assert not [n for n in names if n.endswith(".partial")]
    assert not [n for n in names if ".displaced-" in n]
    if not layout.store_path.exists():
        assert not [
            n for n in names if n.endswith(("-wal", "-shm")) and "set-aside" not in n
        ]
    assert len(set_aside_stores(layout.store_path)) <= 1


def test_join_with_the_flag_frees_the_store_path_and_the_copy_holds_the_mark(
    hub: InProcessHub,
) -> None:
    layout = client_layout()
    make_local_store(layout, "demo")

    report = join(line_for(hub), set_aside_local=True)

    assert report.set_aside is not None
    assert not layout.store_path.exists()
    assert _mark(report.set_aside) is not None
    assert program_ids(report.set_aside) == ["demo"]
    _left_clean(layout)


def test_a_connection_opened_before_the_join_fails_its_next_write_naming_the_hub(
    hub: InProcessHub,
) -> None:
    layout = client_layout()
    make_local_store(layout, "demo")
    early = open_local_store(layout.store_path)
    try:
        join(line_for(hub), set_aside_local=True)

        with pytest.raises(LocalStoreClosedError, match=hub.address), early.write():
            pass
    finally:
        early.close()


def test_leave_puts_the_store_back_with_its_rows_and_the_next_command_writes_to_it(
    hub: InProcessHub,
) -> None:
    layout = client_layout()
    make_local_store(layout, "demo")
    config_path().write_text(example_config_text(), encoding="utf-8")
    report = join(line_for(hub), set_aside_local=True)
    assert report.set_aside is not None

    left = leave()

    assert left.put_back.restored == report.set_aside
    assert not report.set_aside.exists()
    assert program_ids(layout.store_path) == ["demo"]
    assert _mark(layout.store_path) is None
    assert not layout.client_file.exists() and not layout.pinned_cert.exists()
    wiring.invoke(OperationName.STANDING, {"text": "a ruling"}, None, Door.CLI)
    with closing(sqlite3.connect(layout.store_path)) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM standing_answers"
        ).fetchone() == (1,)
    _left_clean(layout)


def test_a_store_set_aside_while_a_reader_is_open_keeps_every_row(
    hub: InProcessHub,
) -> None:
    layout = client_layout()
    make_local_store(layout, "first")
    store = open_local_store(layout.store_path)
    reader = sqlite3.connect(layout.store_path, isolation_level=None)
    try:
        reader.execute("BEGIN")
        reader.execute("SELECT COUNT(*) FROM programs").fetchone()
        with store.write() as transaction:
            transaction.execute(
                "INSERT INTO programs (program_id, registered_at, updated_at, "
                "owner_id) VALUES ('in-the-log', 't', 't', ?)",
                (transaction.acting("programs").owner_id,),
            )
        assert Path(f"{layout.store_path}-wal").stat().st_size > 0

        join(line_for(hub), set_aside_local=True)
        leave()
    finally:
        reader.close()
        store.close()

    assert program_ids(layout.store_path) == ["first", "in-the-log"]


STEPS = [field.name for field in fields(SetAsideHooks)]


@pytest.mark.parametrize("stopped_after", STEPS[:-1])
def test_a_join_stopped_after_a_step_is_finished_by_the_same_join(
    hub: InProcessHub, stopped_after: str
) -> None:
    layout = client_layout()
    make_local_store(layout, "demo")
    keep_side_files = sqlite3.connect(layout.store_path)  # a reader leaves -wal/-shm
    keep_side_files.execute("SELECT COUNT(*) FROM programs").fetchone()
    try:
        with pytest.raises(Stop):
            join(line_for(hub), set_aside_local=True, hooks=_stopped(stopped_after))
        assert not layout.client_file.exists()

        finished = join(line_for(hub), set_aside_local=True)
    finally:
        keep_side_files.close()

    assert layout.client_file.exists()
    assert not layout.store_path.exists()
    assert finished.set_aside is not None
    assert program_ids(finished.set_aside) == ["demo"]
    assert _mark(finished.set_aside) is not None
    _left_clean(layout)


@pytest.mark.parametrize("stopped_after", STEPS)
def test_a_stopped_join_is_ended_by_leave_with_the_store_back(
    hub: InProcessHub, stopped_after: str
) -> None:
    layout = client_layout()
    make_local_store(layout, "demo")
    keep_side_files = sqlite3.connect(layout.store_path)
    keep_side_files.execute("SELECT COUNT(*) FROM programs").fetchone()
    try:
        with pytest.raises(Stop):
            join(line_for(hub), set_aside_local=True, hooks=_stopped(stopped_after))

        leave()
    finally:
        keep_side_files.close()

    assert program_ids(layout.store_path) == ["demo"]
    assert _mark(layout.store_path) is None
    assert not set_aside_stores(layout.store_path)
    _left_clean(layout)


def test_after_a_stop_following_the_mark_local_commands_name_leave_and_the_join(
    hub: InProcessHub,
) -> None:
    layout = client_layout()
    make_local_store(layout, "demo")
    config_path().write_text(example_config_text(), encoding="utf-8")
    with pytest.raises(Stop):
        join(line_for(hub), set_aside_local=True, hooks=_stopped("after_mark"))

    with pytest.raises(LocalStoreClosedError) as raised:
        wiring.invoke(OperationName.STANDING, {"text": "r"}, None, Door.CLI)

    assert "amoeba leave" in str(raised.value)
    assert "amoeba join" in str(raised.value)


def _schema_ten_store(path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    with closing(sqlite3.connect(path, isolation_level=None)) as connection:
        connection.execute("PRAGMA journal_mode=WAL")
        with monkeypatch.context() as patch:
            first = migration_files()[:10]
            patch.setattr(migrations, "migration_files", lambda: first)
            patch.setattr(migrations, "EXPECTED_SCHEMA_VERSION", 10)
            migrations.migrate(connection)
        connection.execute(
            "INSERT INTO programs VALUES ('old-program', NULL, NULL, 't', 't')"
        )


def test_join_as_the_first_command_on_a_schema_ten_store_migrates_it_and_sets_it_aside(
    hub: InProcessHub, monkeypatch: pytest.MonkeyPatch
) -> None:
    layout = client_layout()
    layout.state_home.mkdir(parents=True, exist_ok=True)
    _schema_ten_store(layout.store_path, monkeypatch)

    report = join(line_for(hub), set_aside_local=True)

    assert report.set_aside is not None
    assert not layout.store_path.exists()
    leave()
    with closing(sqlite3.connect(layout.store_path)) as connection:
        version = connection.execute("SELECT version FROM schema_meta").fetchone()[0]
    assert version == EXPECTED_SCHEMA_VERSION
    assert program_ids(layout.store_path) == ["old-program"]


@pytest.mark.parametrize("failure", ["wrong_fingerprint", "hub_down"])
def test_a_failed_join_with_the_flag_changes_nothing_local(
    hub: InProcessHub, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    layout = client_layout()
    layout.state_home.mkdir(parents=True, exist_ok=True)
    _schema_ten_store(layout.store_path, monkeypatch)
    # Close the connection's side files into the store, so the bytes are the store.
    with closing(sqlite3.connect(layout.store_path)) as connection:
        connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    line = line_for(hub)
    if failure == "wrong_fingerprint":
        line = line.replace(line.split(",")[1], "0" * 64)
    else:
        hub.stop()
    before = (files_of(layout.state_home), layout.store_path.read_bytes())

    with pytest.raises((JoinError, HubUnreachableError)):
        join(line, set_aside_local=True)

    assert (files_of(layout.state_home), layout.store_path.read_bytes()) == before
    with closing(sqlite3.connect(layout.store_path)) as connection:
        assert connection.execute("SELECT version FROM schema_meta").fetchone()[0] == 10


def test_a_legacy_store_stops_a_join_without_the_flag_and_is_not_moved(
    hub: InProcessHub, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # The in-process hub keeps its own state under tmp_path/state.
    layout = make_layout(tmp_path / "client")
    legacy_store = seed_legacy_home(layout)
    monkeypatch.setattr(wiring_door, "state_layout", lambda: layout)

    with pytest.raises(JoinError, match="--set-aside-local") as raised:
        join(line_for(hub), set_aside_local=False)

    assert str(legacy_store) in str(raised.value)
    assert legacy_store.exists()
    assert not layout.store_path.exists()


def test_a_leftover_partial_copy_is_replaced_by_join_and_deleted_by_leave(
    hub: InProcessHub,
) -> None:
    layout = client_layout()
    make_local_store(layout, "demo")
    partial = Path(f"{layout.store_path}.set-aside.partial")
    partial.write_bytes(b"half a copy from a killed run")

    join(line_for(hub), set_aside_local=True)

    assert not partial.exists()
    partial.write_bytes(b"another leftover")
    leave()
    assert not partial.exists()
    assert program_ids(layout.store_path) == ["demo"]


def test_a_hand_placed_store_is_displaced_by_leave_and_nothing_is_deleted(
    hub: InProcessHub,
) -> None:
    layout = client_layout()
    make_local_store(layout, "original")
    join(line_for(hub), set_aside_local=True)
    make_local_store(layout, "hand-placed")
    Path(f"{layout.store_path}-wal").write_bytes(b"")

    left = leave()

    displaced = left.put_back.displaced
    assert displaced is not None
    assert program_ids(displaced) == ["hand-placed"]
    assert program_ids(layout.store_path) == ["original"]
    assert displaced.name.startswith("amoeba.sqlite3.displaced-")
    assert not set_aside_stores(layout.store_path)


def test_leave_keeps_only_the_newest_displaced_stores(hub: InProcessHub) -> None:
    layout = client_layout()
    make_local_store(layout, "original")
    join(line_for(hub), set_aside_local=True)
    make_local_store(layout, "hand-placed")
    older = [
        Path(f"{layout.store_path}.displaced-2025010100000{n}Z")
        for n in range(1, DISPLACED_STORES_KEPT + 2)
    ]
    for path in older:
        path.write_bytes(b"an earlier displaced store")
    Path(f"{older[0]}-wal").write_bytes(b"its side file")

    displaced = leave().put_back.displaced

    assert displaced is not None
    everything = layout.store_path.parent.glob("*.displaced-*")
    kept = sorted(p.name for p in everything if not p.name.endswith(("-wal", "-shm")))
    assert not Path(f"{older[0]}-wal").exists()
    assert kept == sorted(
        [p.name for p in older[-(DISPLACED_STORES_KEPT - 1) :]] + [displaced.name]
    )


@pytest.mark.parametrize("marked_differently", [False, True])
def test_join_with_a_set_aside_and_a_hand_placed_store_is_refused_and_deletes_neither(
    hub: InProcessHub, marked_differently: bool
) -> None:
    layout = client_layout()
    make_local_store(layout, "hand-placed")
    aside = Path(f"{layout.store_path}.set-aside-20260101T000000Z")
    aside.write_bytes(layout.store_path.read_bytes())
    if marked_differently:
        for store in (layout.store_path, aside):
            with closing(sqlite3.connect(store)) as connection:
                connection.execute(
                    "INSERT INTO closed_mark VALUES (1, 'other:1', ?)",
                    (f"t-{store.name}",),
                )
                connection.commit()

    with pytest.raises(StoreRelocateError) as raised:
        join(line_for(hub), set_aside_local=True)

    assert str(aside) in str(raised.value)
    assert str(layout.store_path) in str(raised.value)
    assert "amoeba leave" in str(raised.value)
    assert aside.exists() and layout.store_path.exists()
    assert not layout.client_file.exists()


def test_put_back_runs_each_step_only_if_it_is_not_already_done(
    hub: InProcessHub,
) -> None:
    layout = client_layout()
    make_local_store(layout, "demo")
    join(line_for(hub), set_aside_local=True)
    # The leave stopped after the mark was cleared and before the rename.
    (aside,) = set_aside_stores(layout.store_path)
    with closing(sqlite3.connect(aside, isolation_level=None)) as connection:
        connection.execute("DELETE FROM closed_mark")

    leave()

    assert program_ids(layout.store_path) == ["demo"]
    assert not layout.client_file.exists()


def test_hooks_are_exactly_the_steps_of_d4() -> None:
    assert STEPS == [
        "after_mark",
        "after_copy",
        "after_rename",
        "after_store_deleted",
        "after_delete",
    ]
