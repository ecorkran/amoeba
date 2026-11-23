"""``scripts/update_live.py`` against a throwaway home, with install faked."""

from __future__ import annotations

import importlib.util
import sqlite3
import sys
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType

import pytest
import yaml
from store.seed import insert_member, insert_program
from store_open import open_local_store
from user_configs import example_config_text

from amoeba.config.home import config_path, state_layout, store_path
from amoeba.operations.names import OperationName
from amoeba.operations.state_move import open_state_store
from amoeba.store.migrations import EXPECTED_SCHEMA_VERSION
from amoeba.store.store import Store

SCRIPT = Path(__file__).parents[2] / "scripts" / "update_live.py"
NOW = datetime(2026, 11, 15, 12, 0, tzinfo=UTC)
LATER = datetime(2026, 11, 16, 12, 0, tzinfo=UTC)
HEAD = "a" * 40
PREVIOUS = "b" * 40
ALL_TOOLS = {name.value for name in OperationName}


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("update_live", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["update_live"] = module
    spec.loader.exec_module(module)
    return module


update_live = _load()


def _seed_member(store: Store, project_id: str) -> None:
    with store.write() as transaction:
        insert_program(
            transaction,
            program_id=f"p-{project_id}",
            concept_member=None,
            concept_path=None,
            registered_at=NOW,
            updated_at=NOW,
        )
        insert_member(
            transaction,
            project_id=project_id,
            program_id=f"p-{project_id}",
            rules_paths=("CLAUDE.md",),
            authorize_allow=(),
            authorize_deny=(),
            registered_at=NOW,
            updated_at=NOW,
        )


@pytest.fixture
def live(amoeba_home: Path) -> Path:
    """A home with a migrated store holding two members and the example config."""
    store = open_local_store(store_path())
    _seed_member(store, "one")
    _seed_member(store, "two")
    store.close()
    config_path().write_text(example_config_text(), encoding="utf-8")
    return amoeba_home


class FakeSteps:
    def __init__(self, tools: set[str] = ALL_TOOLS) -> None:
        self.installed: list[str] = []
        self.migrations = 0
        self.tools = tools

    def steps(self) -> object:
        return update_live.Steps(
            install=self.installed.append,
            migrate=self._migrate,
            list_tools=lambda: self.tools,
        )

    def _migrate(self) -> None:
        """What `amoeba list` does: the local opener, which migrates the store and
        makes the machine `local`."""
        self.migrations += 1
        open_state_store(state_layout()).close()


def _drop_key(key: str) -> None:
    document = yaml.safe_load(config_path().read_text(encoding="utf-8"))
    del document[key]
    config_path().write_text(yaml.safe_dump(document), encoding="utf-8")


def test_update_backs_up_installs_migrates_and_records(live: Path) -> None:
    fake = FakeSteps()

    added = update_live.update(HEAD, PREVIOUS, fake.steps(), NOW)

    assert added == []
    assert fake.installed == [update_live.install_spec(HEAD)]
    assert fake.migrations == 1
    root = update_live.backups_root()
    backup = update_live.newest_backup()
    assert update_live.member_count(backup / update_live.STORE_BACKUP) == 2
    assert (backup / update_live.CONFIG_BACKUP).exists()
    assert (backup / update_live.PREVIOUS_COMMIT).read_text().strip() == PREVIOUS
    assert (root / update_live.INSTALLED_COMMIT).read_text().strip() == HEAD
    assert update_live.previous_commit(None) == HEAD


def test_a_second_update_deletes_the_older_backup(live: Path) -> None:
    update_live.update(HEAD, PREVIOUS, FakeSteps().steps(), NOW)
    update_live.update(HEAD, HEAD, FakeSteps().steps(), LATER)

    stamps = [p for p in update_live.backups_root().iterdir() if p.is_dir()]
    assert [p.name for p in stamps] == [LATER.strftime("%Y%m%dT%H%M%S")]


def test_a_missing_config_key_is_appended_from_the_example(live: Path) -> None:
    _drop_key("prune_after_days")

    added = update_live.update(HEAD, PREVIOUS, FakeSteps().steps(), NOW)

    assert added == ["prune_after_days"]
    document = yaml.safe_load(config_path().read_text(encoding="utf-8"))
    assert (
        document["prune_after_days"] == update_live.example_values()["prune_after_days"]
    )


def test_a_missing_key_with_no_example_stops_before_installing(live: Path) -> None:
    _drop_key("prune_after_days")
    fake = FakeSteps()
    examples = update_live.example_values()
    del examples["prune_after_days"]

    with pytest.raises(update_live.UpdateError, match="no example"):
        update_live.add_missing_keys(config_path(), examples)
    assert fake.installed == []


def test_a_failed_read_back_restores_store_config_and_tool(live: Path) -> None:
    fake = FakeSteps()
    original_config = config_path().read_text(encoding="utf-8")
    _drop_key("prune_after_days")
    dropped_config = config_path().read_text(encoding="utf-8")

    def lose_a_member() -> None:
        store = open_local_store(store_path())
        with store.write() as transaction:
            transaction.execute("DELETE FROM members WHERE project_id = 'two'")
        store.close()

    steps = update_live.Steps(
        install=fake.installed.append,
        migrate=lose_a_member,
        list_tools=lambda: ALL_TOOLS,
    )
    with pytest.raises(update_live.UpdateError, match="members 1 != 2"):
        update_live.update(HEAD, PREVIOUS, steps, NOW)

    assert update_live.member_count(store_path()) == 2
    assert config_path().read_text(encoding="utf-8") == dropped_config
    assert config_path().read_text(encoding="utf-8") != original_config
    assert fake.installed == [
        update_live.install_spec(HEAD),
        update_live.install_spec(PREVIOUS),
    ]
    assert not (update_live.backups_root() / update_live.INSTALLED_COMMIT).exists()


def test_missing_mcp_tools_fail_the_read_back(live: Path) -> None:
    fake = FakeSteps(tools=ALL_TOOLS - {OperationName.STATUS.value})

    with pytest.raises(update_live.UpdateError, match="tools differ"):
        update_live.update(HEAD, PREVIOUS, fake.steps(), NOW)
    assert fake.installed[-1] == update_live.install_spec(PREVIOUS)


def test_restore_puts_the_newest_backup_back(live: Path) -> None:
    fake = FakeSteps()
    update_live.update(HEAD, PREVIOUS, fake.steps(), NOW)
    held = open_local_store(store_path())  # stays open, as a running server's does
    _seed_member(held, "three")

    restored = update_live.restore(update_live.newest_backup(), fake.steps())

    assert restored == PREVIOUS
    assert update_live.member_count(store_path()) == 2
    with held.read() as transaction:
        rows = transaction.execute("SELECT count(*) FROM members").fetchone()
    assert rows[0] == 2
    held.close()


def test_no_install_record_and_no_previous_is_an_error(live: Path) -> None:
    with pytest.raises(update_live.UpdateError, match="--previous"):
        update_live.previous_commit(None)
    assert update_live.previous_commit(PREVIOUS) == PREVIOUS


def _schema_ten_store(path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A copy of a schema-10 store holding two members: migrations 1 to 10 only."""
    from amoeba.store import migrations

    with closing(sqlite3.connect(path, isolation_level=None)) as connection:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        with monkeypatch.context() as patch:
            first = migrations.migration_files()[:10]
            patch.setattr(migrations, "migration_files", lambda: first)
            patch.setattr(migrations, "EXPECTED_SCHEMA_VERSION", 10)
            migrations.migrate(connection)
        connection.execute(
            "INSERT INTO programs VALUES ('p-one', NULL, NULL, 't', 't')"
        )
        for project in ("one", "two"):
            connection.execute(
                "INSERT INTO members (project_id, program_id, rules_paths, "
                "authorize_allow, authorize_deny, registered_at, updated_at) "
                "VALUES (?, 'p-one', '[]', '[]', '[]', 't', 't')",
                (project,),
            )


def _version(path: Path) -> int:
    with closing(sqlite3.connect(path)) as connection:
        return int(connection.execute("SELECT version FROM schema_meta").fetchone()[0])


def test_update_and_restore_against_a_copy_of_a_schema_ten_store(
    amoeba_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _schema_ten_store(store_path(), monkeypatch)
    config_path().write_text(example_config_text(), encoding="utf-8")
    assert _version(store_path()) == 10
    fake = FakeSteps()

    update_live.update(HEAD, PREVIOUS, fake.steps(), NOW)

    assert _version(store_path()) == EXPECTED_SCHEMA_VERSION
    with closing(sqlite3.connect(store_path())) as connection:
        assert connection.execute("SELECT count(*) FROM owners").fetchone() == (1,)
        assert connection.execute("SELECT name FROM machines").fetchall() == [
            ("local",)
        ]
    backup = update_live.newest_backup()
    assert _version(backup / update_live.STORE_BACKUP) == 10

    restored = update_live.restore(backup, fake.steps())

    assert restored == PREVIOUS
    assert _version(store_path()) == 10
    assert update_live.member_count(store_path()) == 2


def test_a_store_with_no_local_machine_fails_the_read_back(live: Path) -> None:
    def forget_local() -> None:
        with closing(sqlite3.connect(store_path())) as connection:
            connection.execute("DELETE FROM machines")
            connection.commit()

    def install(_spec: str) -> None:
        return None

    steps = update_live.Steps(
        install=install, migrate=forget_local, list_tools=lambda: ALL_TOOLS
    )

    with pytest.raises(update_live.UpdateError, match="machines holds"):
        update_live.update(HEAD, PREVIOUS, steps, NOW)
