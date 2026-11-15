"""``scripts/update_live.py`` against a throwaway home, with install faked."""

from __future__ import annotations

import importlib.util
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType

import pytest
import yaml
from store.seed import insert_member, insert_program
from user_configs import example_config_text

from amoeba.config.home import config_path, store_path
from amoeba.operations.names import OperationName
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
    store = Store.open(store_path())
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
        self.on_migrate: list[object] = []

    def steps(self) -> object:
        return update_live.Steps(
            install=self.installed.append,
            migrate=self._migrate,
            list_tools=lambda: self.tools,
        )

    def _migrate(self) -> None:
        self.migrations += 1
        Store.open(store_path()).close()


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
        store = Store.open(store_path())
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
    held = Store.open(store_path())  # stays open, as a running server's does
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
