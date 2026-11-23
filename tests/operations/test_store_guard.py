"""The guard on both store openers and `prepare_state_home` (slice 260, D2, D12)."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from amoeba.client.client_file import ClientFile, write_client_file
from amoeba.config.home import StateLayout
from amoeba.hub.store_open import open_hub_store
from amoeba.operations.state_move import open_state_store, prepare_state_home
from amoeba.store.errors import (
    HubHomeError,
    HubStoreMissingError,
    LocalStoreClosedError,
)
from operations.state_move_support import make_layout, seed_legacy_home

HUB = "hub.example:8443"


def _tree(root: Path) -> list[str]:
    return sorted(str(p.relative_to(root)) for p in root.rglob("*"))


def _join_files(layout: StateLayout) -> None:
    write_client_file(
        layout.client_file, ClientFile(address=HUB, machine="a", token="t")
    )
    layout.pinned_cert.parent.mkdir(parents=True, exist_ok=True)
    layout.pinned_cert.write_text("cert", encoding="utf-8")


def _tables(path: Path) -> dict[str, int]:
    with closing(sqlite3.connect(path)) as connection:
        names = [
            r[0]
            for r in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' "
                "AND name NOT LIKE 'sqlite_%'"
            )
        ]
        return {
            name: connection.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
            for name in names
        }


@pytest.fixture
def layout(tmp_path: Path) -> StateLayout:
    return make_layout(tmp_path)


def test_a_client_file_stops_both_openers_and_the_move(
    layout: StateLayout, tmp_path: Path
) -> None:
    _join_files(layout)
    before = _tree(tmp_path)

    with pytest.raises(LocalStoreClosedError, match=HUB):
        open_state_store(layout)
    # The hub's opener may not import the client package, so it names the file.
    with pytest.raises(LocalStoreClosedError, match="client file"):
        open_hub_store(layout)
    with pytest.raises(LocalStoreClosedError, match=HUB):
        prepare_state_home(layout)

    assert _tree(tmp_path) == before
    assert not layout.state_home.exists() or not layout.store_path.exists()


def test_a_client_file_stops_a_move_of_a_legacy_store(
    layout: StateLayout, tmp_path: Path
) -> None:
    legacy_store = seed_legacy_home(layout)
    _join_files(layout)

    with pytest.raises(LocalStoreClosedError):
        prepare_state_home(layout)

    assert legacy_store.exists()
    assert not layout.store_path.exists()


def test_a_set_aside_store_and_no_store_makes_the_opener_refuse(
    layout: StateLayout,
) -> None:
    layout.state_home.mkdir(parents=True)
    aside = layout.state_home / "amoeba.sqlite3.set-aside-20261121T100000Z"
    aside.write_bytes(b"")
    legacy_store = seed_legacy_home(layout)
    before = _tree(layout.state_home)

    with pytest.raises(LocalStoreClosedError, match="amoeba leave") as raised:
        open_state_store(layout)

    assert aside.name in str(raised.value)
    assert _tree(layout.state_home) == before
    assert legacy_store.exists()


def test_open_hub_store_on_a_fresh_home_refuses_and_changes_nothing(
    layout: StateLayout, tmp_path: Path
) -> None:
    before = _tree(tmp_path)

    with pytest.raises(HubStoreMissingError, match="amoeba hub serve"):
        open_hub_store(layout)

    assert _tree(tmp_path) == before
    assert not layout.state_home.exists()


def test_open_hub_store_with_create_makes_a_store_with_no_local_machine(
    layout: StateLayout,
) -> None:
    open_hub_store(layout, create=True).close()

    assert _tables(layout.store_path)["machines"] == 0
    assert _tables(layout.store_path)["owners"] == 1


def test_a_hub_home_refuses_the_local_opener_and_the_move(
    layout: StateLayout,
) -> None:
    open_hub_store(layout, create=True).close()
    layout.hub_file.parent.mkdir(parents=True, exist_ok=True)
    layout.hub_file.write_text("bind: x\n", encoding="utf-8")
    rows_before = _tables(layout.store_path)

    with pytest.raises(HubHomeError, match="hub"):
        open_state_store(layout)
    with pytest.raises(HubHomeError):
        prepare_state_home(layout)

    assert _tables(layout.store_path) == rows_before
    assert rows_before["machines"] == 0


def test_the_hub_opener_still_opens_a_hub_home(layout: StateLayout) -> None:
    open_hub_store(layout, create=True).close()
    layout.hub_file.parent.mkdir(parents=True, exist_ok=True)
    layout.hub_file.write_text("bind: x\n", encoding="utf-8")

    open_hub_store(layout).close()
