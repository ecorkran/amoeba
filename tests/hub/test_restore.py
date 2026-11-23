"""``--from-backup``: restoring a backup into the state directory (slice 260, D14)."""

from __future__ import annotations

import shutil
import sqlite3
from collections.abc import Callable
from contextlib import closing
from dataclasses import fields
from datetime import timedelta
from pathlib import Path

import pytest

from amoeba.config.home import StateLayout
from amoeba.hub.errors import HubStartError
from amoeba.hub.restore import (
    PARTIAL_DIR_NAME,
    REPLACED_PREFIX,
    RestoreHooks,
    restore_from_backup,
)
from amoeba.hub.start import StartHooks, prepare_start
from amoeba.store.store import Store
from hub.call_support import NOW
from hub.start_support import (
    backup_of,
    complete_state,
    hub_home,
    programs,
    tree,
)

FILES = ("amoeba.sqlite3", "hub-cert.pem", "hub-key.pem")
KEPT = 2


class Stop(Exception):
    """A test's own stop, raised from a hook."""


@pytest.fixture
def source(tmp_path: Path) -> tuple[StateLayout, Path, Path]:
    """A hub with a backup of its state; returns the layout, backups, the backup."""
    layout, backup_dir = hub_home(tmp_path)
    complete_state(layout)
    return layout, backup_dir, backup_of(layout, backup_dir)


def _empty_state(tmp_path: Path) -> Path:
    state = tmp_path / "fresh-state"
    state.mkdir()
    return state


def _rows(store: Path) -> list[str]:
    with closing(sqlite3.connect(store)) as connection:
        return [r[0] for r in connection.execute("SELECT program_id FROM programs")]


def test_a_restore_into_an_empty_state_serves_the_backups_rows_and_certificate(
    tmp_path: Path, source: tuple[StateLayout, Path, Path]
) -> None:
    layout, _backup_dir, backup = source
    state = _empty_state(tmp_path)

    replaced = restore_from_backup(backup, state, NOW, KEPT)

    assert replaced is None
    assert _rows(state / "amoeba.sqlite3") == ["demo"]
    assert (state / "hub-cert.pem").read_bytes() == layout.hub_cert.read_bytes()
    assert (state / "hub-key.pem").read_bytes() == layout.hub_key.read_bytes()
    assert not [p for p in state.iterdir() if p.name.startswith(REPLACED_PREFIX)]
    assert not (state / PARTIAL_DIR_NAME).exists()


def test_a_restore_over_a_working_hub_refuses_naming_the_files_and_changes_nothing(
    source: tuple[StateLayout, Path, Path],
) -> None:
    layout, _backup_dir, backup = source
    before = tree(layout.state_home)

    with pytest.raises(HubStartError) as raised:
        restore_from_backup(backup, layout.state_home, NOW, KEPT)

    assert all(name in str(raised.value) for name in FILES)
    assert tree(layout.state_home) == before


def test_a_restore_over_a_store_with_no_certificate_moves_it_to_replaced(
    tmp_path: Path, source: tuple[StateLayout, Path, Path]
) -> None:
    layout, _backup_dir, backup = source
    state = layout.state_home
    layout.hub_cert.unlink()
    layout.hub_key.unlink()
    Path(f"{layout.store_path}-wal").write_bytes(b"")

    replaced = restore_from_backup(backup, state, NOW, KEPT)

    assert replaced is not None and replaced.parent == state
    assert replaced.name.startswith(REPLACED_PREFIX)
    assert (replaced / "amoeba.sqlite3").exists()
    assert (replaced / "amoeba.sqlite3-wal").exists()
    assert _rows(replaced / "amoeba.sqlite3") == ["demo"]
    assert _rows(state / "amoeba.sqlite3") == ["demo"]
    assert (state / "hub-cert.pem").exists()


def test_a_backup_with_a_file_missing_is_refused_with_the_state_unchanged(
    tmp_path: Path, source: tuple[StateLayout, Path, Path]
) -> None:
    _layout, _backup_dir, backup = source
    (backup / "hub-key.pem").unlink()
    state = _empty_state(tmp_path)

    with pytest.raises(HubStartError, match="hub-key.pem"):
        restore_from_backup(backup, state, NOW, KEPT)

    assert tree(state) == []


def test_a_backup_whose_store_is_not_a_database_is_refused(
    tmp_path: Path, source: tuple[StateLayout, Path, Path]
) -> None:
    _layout, _backup_dir, backup = source
    (backup / "amoeba.sqlite3").write_bytes(b"this is not a database at all" * 100)
    state = _empty_state(tmp_path)

    with pytest.raises(HubStartError, match="database"):
        restore_from_backup(backup, state, NOW, KEPT)

    assert tree(state) == []


HOOKS = [field.name for field in fields(RestoreHooks)]


@pytest.mark.parametrize("stopped_after", HOOKS)
def test_a_stopped_restore_blocks_a_plain_start_and_the_same_command_finishes_it(
    tmp_path: Path, source: tuple[StateLayout, Path, Path], stopped_after: str
) -> None:
    layout, backup_dir, backup = source
    # A damaged hub: the store is there, the certificate is not.
    layout.hub_cert.unlink()
    layout.hub_key.unlink()

    def stop() -> None:
        raise Stop

    hooks: dict[str, Callable[[], None]] = {stopped_after: stop}
    with pytest.raises(Stop):
        restore_from_backup(backup, layout.state_home, NOW, KEPT, RestoreHooks(**hooks))

    assert (layout.state_home / PARTIAL_DIR_NAME).exists()
    with pytest.raises(HubStartError, match="did not finish"):
        prepare_start(layout, now=NOW, start_log=lambda _config: None)

    prepared = prepare_start(
        layout, now=NOW, start_log=lambda _config: None, from_backup=backup
    )
    prepared.listener.close()

    assert programs(layout) == ["demo"]
    assert layout.hub_cert.exists() and layout.hub_key.exists()
    assert not (layout.state_home / PARTIAL_DIR_NAME).exists()
    assert backup_dir.exists()


def test_after_a_finished_restore_the_same_restore_is_refused_as_a_working_hub(
    tmp_path: Path, source: tuple[StateLayout, Path, Path]
) -> None:
    _layout, _backup_dir, backup = source
    state = _empty_state(tmp_path)
    restore_from_backup(backup, state, NOW, KEPT)

    with pytest.raises(HubStartError, match="working hub"):
        restore_from_backup(backup, state, NOW, KEPT)


def test_a_restored_store_opens_through_the_hub_opener(
    tmp_path: Path, source: tuple[StateLayout, Path, Path]
) -> None:
    _layout, _backup_dir, backup = source
    state = _empty_state(tmp_path)
    restore_from_backup(backup, state, NOW, KEPT)

    with Store.open(state / "amoeba.sqlite3") as store, store.read() as tx:
        assert tx.execute("SELECT COUNT(*) FROM owners").fetchone()[0] == 1


def test_start_hooks_default_to_no_restore_hooks() -> None:
    assert StartHooks().restore == RestoreHooks()


def test_only_the_newest_kept_replaced_directories_stay(
    tmp_path: Path, source: tuple[StateLayout, Path, Path]
) -> None:
    _layout, _backup_dir, backup = source
    state = _empty_state(tmp_path)
    made: list[Path] = []
    for round_number in range(KEPT + 2):
        # A damaged state each time: a store with no certificate and no key.
        shutil.copy(backup / "amoeba.sqlite3", state / "amoeba.sqlite3")
        for name in ("hub-cert.pem", "hub-key.pem"):
            (state / name).unlink(missing_ok=True)
        replaced = restore_from_backup(
            backup, state, NOW + timedelta(seconds=round_number), KEPT
        )
        assert replaced is not None
        made.append(replaced)

    left = sorted(p for p in state.iterdir() if p.name.startswith(REPLACED_PREFIX))
    assert left == sorted(made[-KEPT:])


def test_a_backup_given_as_a_relative_path_restores(
    tmp_path: Path,
    source: tuple[StateLayout, Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _layout, _backup_dir, backup = source
    state = _empty_state(tmp_path)
    monkeypatch.chdir(backup.parent)

    replaced = restore_from_backup(Path(backup.name), state, NOW, KEPT)

    assert replaced is None
    assert _rows(state / "amoeba.sqlite3") == ["demo"]
