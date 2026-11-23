"""Naming the members that exist (slice 261, D2, D4)."""

from __future__ import annotations

import json
import logging
import subprocess
import time
from collections.abc import Callable, Iterator, Sequence
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn

import pytest
from cf_fixtures import fake_cf_run
from cli.cli_support import run_amoeba, write_config
from git_repo import git, make_repo
from load.lock_probe import write_lock_is_held
from store.schema_11 import OldMember, build_schema_11_store
from store_open import open_local_store

from amoeba.cli.exit_codes import EXIT_ERROR, EXIT_OK
from amoeba.config.home import store_path
from amoeba.hub.store_open import open_hub_store
from amoeba.operations import here, naming, state_move
from amoeba.operations.errors import ContextForgeError
from amoeba.operations.naming import name_members
from amoeba.operations.state_move import open_state_store
from amoeba.store.checkouts import checkouts_of_member
from amoeba.store.errors import StoreError
from amoeba.store.models import Member
from amoeba.store.programs import get_member_any
from amoeba.store.store import Store, Transaction
from operations.state_move_support import make_layout

SSH_ORIGIN = "git@github.com:org/forge.git"
HTTPS_ORIGIN = "https://github.com/Org/Forge/"
REDUCED = "github.com/org/forge"


@dataclass(frozen=True)
class Listed:
    """One project as ``cf list projects --json`` gives it."""

    project_id: str
    name: str
    path: Path | None


def cf_listing(*projects: Listed) -> Callable[..., subprocess.CompletedProcess[str]]:
    def run(argv: Sequence[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        entries = [
            {"id": p.project_id, "name": p.name}
            | ({} if p.path is None else {"projectPath": str(p.path)})
            for p in projects
        ]
        return subprocess.CompletedProcess(list(argv), 0, json.dumps(entries), "")

    return run


def _repo(tmp_path: Path, name: str, origin: str | None) -> Path:
    repo = make_repo(tmp_path / name)
    if origin is not None:
        git(repo, "remote", "add", "origin", origin)
    return repo


@dataclass
class World:
    """A schema-11 store of seven members and the ``cf`` that lists them."""

    store: Store
    cf: Callable[..., subprocess.CompletedProcess[str]]
    paths: dict[str, Path]


def _git_must_not_run(*_args: object, **_kwargs: object) -> NoReturn:
    raise AssertionError("git must not run")


def _world(tmp_path: Path) -> World:
    paths = {
        "id-a": _repo(tmp_path, "a", SSH_ORIGIN),
        "id-b": _repo(tmp_path, "b", HTTPS_ORIGIN),
        "id-e": _repo(tmp_path, "e", None),
        "id-f": _repo(tmp_path, "f", "https://github.com/org/other.git"),
        "id-h": _repo(tmp_path, "h", "/srv/git/local.git"),
    }
    database = tmp_path / "old.sqlite3"
    build_schema_11_store(
        database,
        [
            OldMember("id-a", wake_command="make go"),
            OldMember("id-b"),
            OldMember("id-c"),
            OldMember("id-d", wake_command="lost"),
            OldMember("id-e"),
            OldMember("id-f"),
            OldMember("id-g", removed=True),
            OldMember("id-h"),
        ],
    )
    cf = cf_listing(
        Listed("id-a", "forge", paths["id-a"]),
        Listed("id-b", "Forge", paths["id-b"]),
        Listed("id-d", "nopath", None),
        Listed("id-e", "has space", paths["id-e"]),
        Listed("id-f", "ID-A", paths["id-f"]),
        Listed("id-g", "forge", None),
        Listed("id-h", "localrepo", paths["id-h"]),
    )
    return World(open_local_store(database), cf, paths)


@pytest.fixture
def world(tmp_path: Path) -> Iterator[World]:
    opened = _world(tmp_path)
    name_members(opened.store, opened.cf, subprocess.run)
    yield opened
    opened.store.close()


def _member(world: World, project_id: str) -> Member:
    with world.store.read() as transaction:
        member = get_member_any(transaction, project_id)
    assert member is not None
    return member


def test_every_member_is_named(world: World) -> None:
    names = {
        pid: _member(world, pid).name for pid in "abcdefgh" for pid in (f"id-{pid}",)
    }

    assert names == {
        "id-a": "forge",
        "id-b": "id-b",
        "id-c": "id-c",
        "id-d": "nopath",
        "id-e": "id-e",
        "id-f": "id-f",
        "id-g": "forge",
        "id-h": "localrepo",
    }


def test_a_member_cf_does_not_list_is_named_by_its_id_with_no_checkout(
    world: World,
) -> None:
    with world.store.read() as transaction:
        assert checkouts_of_member(transaction, "id-c") == ()
    assert _member(world, "id-c").origin is None


def test_the_first_registered_of_two_with_one_name_has_it(world: World) -> None:
    assert _member(world, "id-a").name == "forge"
    assert _member(world, "id-b").name == "id-b"


def test_a_name_the_pattern_refuses_gives_the_id(world: World) -> None:
    assert _member(world, "id-e").name == "id-e"


def test_a_name_that_is_another_members_id_gives_the_members_own_id(
    world: World,
) -> None:
    assert _member(world, "id-f").name == "id-f"


def test_each_listed_member_with_a_path_has_a_local_checkout_with_its_wake_command(
    world: World,
) -> None:
    with world.store.read() as transaction:
        checkouts = checkouts_of_member(transaction, "id-a")
        local_machine = transaction.execute(
            "SELECT machine_id FROM machines WHERE name = 'local'"
        ).fetchone()[0]

    assert len(checkouts) == 1
    assert checkouts[0].machine_id == local_machine
    assert checkouts[0].path == str(world.paths["id-a"])
    assert checkouts[0].cf_project_id == "id-a"
    assert checkouts[0].wake_command == "make go"


def test_the_old_wake_column_is_unchanged_until_it_is_nulled(world: World) -> None:
    with world.store.read() as transaction:
        commands = transaction.execute(
            "SELECT project_id, wake_command FROM members "
            "WHERE wake_command IS NOT NULL ORDER BY project_id"
        ).fetchall()

    assert [tuple(row) for row in commands] == [("id-a", "make go"), ("id-d", "lost")]


def test_a_member_with_no_path_has_no_checkout(world: World) -> None:
    with world.store.read() as transaction:
        assert checkouts_of_member(transaction, "id-d") == ()


def test_of_two_members_with_one_origin_the_first_keeps_it_and_the_second_has_none(
    world: World,
) -> None:
    assert _member(world, "id-a").origin == REDUCED
    assert _member(world, "id-b").origin is None


def test_the_member_that_lost_its_origin_is_logged(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    opened = _world(tmp_path)
    with caplog.at_level(logging.WARNING):
        name_members(opened.store, opened.cf, subprocess.run)

    assert "id-b" in caplog.text
    assert "id-a" in caplog.text
    opened.store.close()


def test_a_removed_member_has_no_checkout_and_keeps_a_name_an_active_one_has(
    world: World,
) -> None:
    with world.store.read() as transaction:
        assert checkouts_of_member(transaction, "id-g") == ()
    removed = _member(world, "id-g")
    assert removed.name == _member(world, "id-a").name == "forge"
    assert removed.removed_at is not None


@pytest.mark.parametrize(
    "project_id",
    ["id-e", "id-h", "id-c"],
    ids=["no origin remote", "address with no host", "not listed"],
)
def test_origin_is_null_when_there_is_none_to_read(
    world: World, project_id: str
) -> None:
    assert _member(world, project_id).origin is None


def test_a_missing_path_and_a_non_repo_path_give_a_null_origin(tmp_path: Path) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()
    database = tmp_path / "old.sqlite3"
    build_schema_11_store(database, [OldMember("id-1"), OldMember("id-2")])
    cf = cf_listing(
        Listed("id-1", "one", plain), Listed("id-2", "two", tmp_path / "missing")
    )

    with open_local_store(database) as store:
        name_members(store, cf, _git_must_not_run)
        with store.read() as transaction:
            origins = [get_member_any(transaction, p) for p in ("id-1", "id-2")]
            assert [m.origin if m else "absent" for m in origins] == [None, None]
            assert len(checkouts_of_member(transaction, "id-1")) == 1


def test_two_calls_at_once_write_once(tmp_path: Path) -> None:
    opened = _world(tmp_path)
    calls = {"count": 0}
    nested: dict[str, object] = {}

    def git_that_lets_a_second_call_finish(
        argv: Sequence[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        calls["count"] += 1
        if calls["count"] == 1:
            # A second call gathers and writes while the first is still gathering.
            name_members(opened.store, opened.cf, subprocess.run)
            with opened.store.read() as transaction:
                nested["named"] = _member_snapshot(transaction)
        return subprocess.run(list(argv), **kwargs)  # type: ignore[call-overload]

    name_members(opened.store, opened.cf, git_that_lets_a_second_call_finish)

    with opened.store.read() as transaction:
        assert _member_snapshot(transaction) == nested["named"]
    opened.store.close()


def _member_snapshot(transaction: Transaction) -> list[tuple[object, ...]]:
    members = transaction.execute(
        "SELECT project_id, name, origin, updated_at FROM members ORDER BY project_id"
    ).fetchall()
    checkouts = transaction.execute(
        "SELECT member_id, path, wake_command, added_at FROM checkouts "
        "ORDER BY member_id"
    ).fetchall()
    return [tuple(row) for row in (*members, *checkouts)]


def test_a_cf_failure_raises_writes_nothing_and_a_later_call_names_them(
    tmp_path: Path,
) -> None:
    opened = _world(tmp_path)

    with pytest.raises(ContextForgeError):
        name_members(opened.store, fake_cf_run(None), subprocess.run)
    with opened.store.read() as transaction:
        unnamed = transaction.execute(
            "SELECT COUNT(*) FROM members WHERE name IS NULL"
        ).fetchone()[0]
        checkouts = transaction.execute("SELECT COUNT(*) FROM checkouts").fetchone()[0]
    assert (unnamed, checkouts) == (8, 0)

    name_members(opened.store, opened.cf, subprocess.run)
    assert _member(World(opened.store, opened.cf, {}), "id-a").name == "forge"
    opened.store.close()


def test_a_hanging_git_ends_within_the_budget_and_the_unread_have_no_origin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(naming, "NAMING_GIT_SECONDS", 0.15)
    monkeypatch.setattr(here, "ORIGIN_READ_TIMEOUT_SECONDS", 0.2)
    opened = _world(tmp_path)
    attempts: list[str] = []

    def hanging_git(argv: Sequence[str], **kwargs: object) -> NoReturn:
        attempts.append(str(kwargs["cwd"]))
        time.sleep(float(str(kwargs["timeout"])))
        raise subprocess.TimeoutExpired(list(argv), float(str(kwargs["timeout"])))

    started = time.monotonic()
    with caplog.at_level(logging.WARNING):
        name_members(opened.store, opened.cf, hanging_git)
    elapsed = time.monotonic() - started

    assert elapsed < 0.15 + 0.2 + 1.0
    assert len(attempts) == 1 or len(attempts) == 2
    assert "ran out" in caplog.text
    with opened.store.read() as transaction:
        origins = transaction.execute("SELECT origin FROM members").fetchall()
    assert all(row[0] is None for row in origins)
    opened.store.close()


def test_no_cf_or_git_runs_while_the_write_lock_is_held(tmp_path: Path) -> None:
    opened = _world(tmp_path)
    held: list[bool] = []

    def probing_cf(
        argv: Sequence[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        held.append(write_lock_is_held(opened.store.path))
        return opened.cf(argv, **kwargs)

    def probing_git(
        argv: Sequence[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        held.append(write_lock_is_held(opened.store.path))
        return subprocess.run(list(argv), **kwargs)  # type: ignore[call-overload]

    name_members(opened.store, probing_cf, probing_git)

    assert len(held) > 2
    assert not any(held)
    opened.store.close()


def test_a_named_store_makes_no_cf_or_git_call(world: World) -> None:
    def fail(*_args: object, **_kwargs: object) -> NoReturn:
        raise AssertionError("no call expected")

    name_members(world.store, fail, fail)


def _do_nothing(*_args: object, **_kwargs: object) -> None:
    return None


def test_without_the_naming_step_the_first_member_read_names_the_member(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    layout = make_layout(tmp_path)
    build_schema_11_store(layout.store_path, [OldMember("id-a")])
    monkeypatch.setattr(state_move, "name_members", _do_nothing)

    with open_state_store(layout) as store, store.read() as transaction:
        with pytest.raises(StoreError, match="id-a"):
            get_member_any(transaction, "id-a")


def test_open_state_store_fails_loudly_when_cf_cannot_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    layout = make_layout(tmp_path)
    build_schema_11_store(layout.store_path, [OldMember("id-a")])
    (tmp_path / "empty-bin").mkdir()
    monkeypatch.setenv("PATH", str(tmp_path / "empty-bin"))

    with pytest.raises(ContextForgeError):
        open_state_store(layout)


def test_the_cli_exits_three_when_cf_fails_and_names_the_members_later(
    tmp_path: Path,
) -> None:
    write_config()
    build_schema_11_store(store_path(), [OldMember("id-a"), OldMember("id-b")])

    failed = run_amoeba(tmp_path, "list", "members", cf_fixture=None)
    assert failed.returncode == EXIT_ERROR
    assert "ContextForgeError" in failed.stderr

    worked = run_amoeba(tmp_path, "list", "members")
    assert worked.returncode == EXIT_OK
    with open_local_store(store_path()) as store:
        assert _member(World(store, fake_cf_run(None), {}), "id-a").name == "id-a"


def test_a_hub_store_names_each_member_by_its_id_and_makes_no_checkout_or_machine(
    tmp_path: Path,
) -> None:
    layout = make_layout(tmp_path)
    build_schema_11_store(
        layout.store_path, [OldMember("id-a", wake_command="x"), OldMember("id-b")]
    )

    with open_hub_store(layout) as store:
        with store.read() as transaction:
            rows = transaction.execute(
                "SELECT project_id, name FROM members ORDER BY project_id"
            ).fetchall()
            counts = [
                transaction.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                for table in ("checkouts", "machines")
            ]
    assert [tuple(row) for row in rows] == [("id-a", "id-a"), ("id-b", "id-b")]
    assert counts == [0, 0]


def test_a_named_hub_store_opens_without_taking_the_write_lock(
    tmp_path: Path,
) -> None:
    layout = make_layout(tmp_path)
    build_schema_11_store(layout.store_path, [OldMember("id-a")])
    open_hub_store(layout).close()

    import sqlite3

    with closing(sqlite3.connect(layout.store_path, isolation_level=None)) as holder:
        holder.execute("BEGIN IMMEDIATE")
        with open_hub_store(layout):
            pass
        holder.execute("ROLLBACK")
