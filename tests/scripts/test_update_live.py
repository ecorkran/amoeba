"""``scripts/update_live.py`` against a throwaway home, with install faked."""

from __future__ import annotations

import importlib.util
import json
import os
import sqlite3
import stat
import subprocess
import sys
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
import yaml
from store.schema_11 import SCHEMA_ELEVEN, OldMember, build_schema_11_store
from store.schema_12 import (
    QUESTION_COUNT,
    SCHEMA_TWELVE,
    WAKE_COUNT,
    build_schema_12_store,
)
from store.schema_13 import build_schema_13_store
from store.seed import insert_member, insert_program
from store_open import open_local_store
from user_configs import example_config_text

from amoeba.config.home import config_path, state_layout, store_path
from amoeba.operations.names import OperationName
from amoeba.operations.runs_document import RunsDocument
from amoeba.operations.state_move import open_state_store
from amoeba.operations.status_machines import store_calling_runs
from amoeba.store.machines import list_machines
from amoeba.store.migrations import EXPECTED_SCHEMA_VERSION
from amoeba.store.store import Store

SCRIPT = Path(__file__).parents[2] / "scripts" / "update_live.py"
NOW = datetime(2026, 11, 15, 12, 0, tzinfo=UTC)
LATER = datetime(2026, 11, 16, 12, 0, tzinfo=UTC)
VERSION = "0.2.8"
PREVIOUS = "0.2.7"
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


def fake_status() -> dict[str, Any]:
    """What ``amoeba status -j`` leaves: this machine's runs report stored, and a
    document whose ``machines`` lists the machines the store holds."""
    with closing(open_state_store(state_layout())) as store:
        store_calling_runs(store, RunsDocument(), NOW)
        with store.read() as transaction:
            rows = list_machines(transaction)
    return {"machines": [{"name": row.name} for row in rows]}


class FakeSteps:
    """The steps ``update`` and ``restore`` call, over fakes.

    ``cf_ids`` is what ``cf list projects`` lists with a path. With ``naming`` the
    migration is ``amoeba list`` as it really runs: ``open_state_store`` under a ``cf``
    stub on ``PATH`` that lists ``stub_projects``, so it names the members and gives
    each listed member with a path its checkout."""

    def __init__(
        self,
        tools: set[str] = ALL_TOOLS,
        *,
        naming: bool = False,
        cf_ids: set[str] | None = None,
    ) -> None:
        self.installed: list[str] = []
        self.migrations = 0
        self.tools = tools
        self.naming = naming
        self.cf_ids: set[str] = set() if cf_ids is None else cf_ids
        self.stub_projects: list[dict[str, str]] = []
        self.bin_dir: Path | None = None
        self.patch: pytest.MonkeyPatch | None = None

    def steps(self) -> object:
        return update_live.Steps(
            install=self.installed.append,
            migrate=self._migrate,
            cf_projects=lambda: self.cf_ids,
            list_tools=lambda: self.tools,
            status=fake_status,
        )

    def _migrate(self) -> None:
        """What `amoeba list` does: the local opener, which migrates the store and
        makes the machine `local`; with ``naming``, under the ``cf`` stub."""
        self.migrations += 1
        if self.naming:
            assert self.bin_dir is not None and self.patch is not None
            _write_cf_projects(self.bin_dir, self.stub_projects)
            self.patch.setenv("PATH", f"{self.bin_dir}{os.pathsep}{os.environ['PATH']}")
        open_state_store(state_layout()).close()


def _write_cf_projects(bin_dir: Path, projects: list[dict[str, str]]) -> None:
    """A ``cf`` that answers ``list projects --json`` with ``projects`` and fails any
    other command."""
    bin_dir.mkdir(parents=True, exist_ok=True)
    document = json.dumps(projects)
    script = bin_dir / "cf"
    script.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = "list" ] && [ "$2" = "projects" ]; then\n'
        f"  cat <<'EOF'\n{document}\nEOF\n"
        "  exit 0\nfi\n"
        "echo 'stub cf: unexpected command' >&2\nexit 1\n",
        encoding="utf-8",
    )
    script.chmod(script.stat().st_mode | stat.S_IXUSR)


def _drop_key(key: str) -> None:
    document = yaml.safe_load(config_path().read_text(encoding="utf-8"))
    del document[key]
    config_path().write_text(yaml.safe_dump(document), encoding="utf-8")


def test_update_backs_up_installs_the_release_from_pypi_and_migrates(
    live: Path,
) -> None:
    fake = FakeSteps()

    added = update_live.update(VERSION, PREVIOUS, fake.steps(), NOW)

    assert added == []
    assert fake.installed == ["amoeba-ai>=0.2.8"]
    assert fake.migrations == 1
    backup = update_live.newest_backup()
    assert update_live.member_count(backup / update_live.STORE_BACKUP) == 2
    assert (backup / update_live.CONFIG_BACKUP).exists()
    assert (backup / update_live.PREVIOUS_VERSION).read_text().strip() == PREVIOUS


def test_restore_reinstalls_the_exact_previous_version() -> None:
    assert update_live.restore_spec(PREVIOUS) == "amoeba-ai==0.2.7"


def test_a_second_update_deletes_the_older_backup(live: Path) -> None:
    update_live.update(VERSION, PREVIOUS, FakeSteps().steps(), NOW)
    update_live.update(VERSION, VERSION, FakeSteps().steps(), LATER)

    stamps = [p for p in update_live.backups_root().iterdir() if p.is_dir()]
    assert [p.name for p in stamps] == [LATER.strftime("%Y%m%dT%H%M%S")]


def test_a_missing_config_key_is_appended_from_the_example(live: Path) -> None:
    _drop_key("prune_after_days")

    added = update_live.update(VERSION, PREVIOUS, FakeSteps().steps(), NOW)

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
        cf_projects=set,
        list_tools=lambda: ALL_TOOLS,
        status=fake_status,
    )
    with pytest.raises(update_live.UpdateError, match="members 1 != 2"):
        update_live.update(VERSION, PREVIOUS, steps, NOW)

    assert update_live.member_count(store_path()) == 2
    assert config_path().read_text(encoding="utf-8") == dropped_config
    assert config_path().read_text(encoding="utf-8") != original_config
    assert fake.installed == [
        update_live.install_spec(VERSION),
        update_live.restore_spec(PREVIOUS),
    ]


def test_missing_mcp_tools_fail_the_read_back(live: Path) -> None:
    fake = FakeSteps(tools=ALL_TOOLS - {OperationName.STATUS.value})

    with pytest.raises(update_live.UpdateError, match="tools differ"):
        update_live.update(VERSION, PREVIOUS, fake.steps(), NOW)
    assert fake.installed[-1] == update_live.restore_spec(PREVIOUS)


def test_restore_puts_the_newest_backup_back(live: Path) -> None:
    fake = FakeSteps()
    update_live.update(VERSION, PREVIOUS, fake.steps(), NOW)
    held = open_local_store(store_path())  # stays open, as a running server's does
    _seed_member(held, "three")

    restored = update_live.restore(update_live.newest_backup(), fake.steps())

    assert restored == PREVIOUS
    assert update_live.member_count(store_path()) == 2
    with held.read() as transaction:
        rows = transaction.execute("SELECT count(*) FROM members").fetchone()
    assert rows[0] == 2
    held.close()


def test_a_version_not_on_pypi_is_an_update_error_not_a_traceback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def uv_fails(command: list[str], **_: object) -> None:
        raise subprocess.CalledProcessError(1, command)

    monkeypatch.setattr(update_live.subprocess, "run", uv_fails)

    with pytest.raises(update_live.UpdateError, match="on PyPI yet"):
        update_live._uv_install(update_live.install_spec(VERSION))  # pyright: ignore[reportPrivateUsage]


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

    update_live.update(VERSION, PREVIOUS, fake.steps(), NOW)

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


def test_update_and_restore_against_a_copy_of_a_schema_13_store(
    amoeba_home: Path,
) -> None:
    build_schema_13_store(store_path())
    config_path().write_text(example_config_text(), encoding="utf-8")
    fake = FakeSteps()

    update_live.update(VERSION, PREVIOUS, fake.steps(), NOW)

    assert _version(store_path()) == EXPECTED_SCHEMA_VERSION
    with closing(sqlite3.connect(store_path())) as connection:
        assert connection.execute("SELECT count(*) FROM machine_runs").fetchone() == (
            1,
        )
    backup = update_live.newest_backup()
    assert _version(backup / update_live.STORE_BACKUP) == 13

    restored = update_live.restore(backup, fake.steps())

    assert restored == PREVIOUS
    assert _version(store_path()) == 13


def test_a_status_without_the_local_machine_or_its_runs_row_fails(
    live: Path,
) -> None:
    failures = update_live.check_status({"machines": [{"name": "beta"}]})

    assert len(failures) == 2
    assert "status machines" in failures[0]
    assert "machine_runs holds []" in failures[1]


def test_a_status_with_another_machine_beside_local_has_no_machines_failure(
    live: Path,
) -> None:
    document = {
        "machines": [{"name": update_live.LOCAL_MACHINE_NAME}, {"name": "beta"}]
    }

    failures = update_live.check_status(document)

    assert not any("status machines" in failure for failure in failures)


def test_a_store_with_no_local_machine_fails_the_read_back(live: Path) -> None:
    def forget_local() -> None:
        with closing(sqlite3.connect(store_path())) as connection:
            connection.execute("DELETE FROM machines")
            connection.commit()

    def install(_spec: str) -> None:
        return None

    steps = update_live.Steps(
        install=install,
        migrate=forget_local,
        cf_projects=set,
        list_tools=lambda: ALL_TOOLS,
        status=fake_status,
    )

    with pytest.raises(update_live.UpdateError, match="machines holds"):
        update_live.update(VERSION, PREVIOUS, steps, NOW)


# --- the live store at schema 11: names, checkouts and the killed update (261 D16) ---


@pytest.fixture
def old_live(
    amoeba_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> FakeSteps:
    """A schema-11 live store with members ``one`` and ``two`` in the throwaway home,
    the example config, and ``FakeSteps`` with naming whose ``cf`` lists both with a
    path and says so to the read-back."""
    build_schema_11_store(store_path(), [OldMember("one"), OldMember("two")])
    config_path().write_text(example_config_text(), encoding="utf-8")
    update_live.backups_root().mkdir(parents=True)
    update_live.record_installed(PREVIOUS)
    fake = FakeSteps(naming=True, cf_ids={"one", "two"})
    fake.bin_dir = tmp_path / "cf-bin"
    fake.patch = monkeypatch
    for member in ("one", "two"):
        directory = tmp_path / "repos" / member
        directory.mkdir(parents=True)
        fake.stub_projects.append(
            {"id": member, "name": f"{member}-name", "projectPath": str(directory)}
        )
    return fake


def _backups() -> list[Path]:
    return update_live.backup_sets()


def _installed_record() -> str | None:
    return update_live.recorded_version()


def test_update_names_the_members_and_passes_both_new_checks(
    old_live: FakeSteps,
) -> None:
    update_live.update(VERSION, PREVIOUS, old_live.steps(), NOW)

    assert _version(store_path()) == EXPECTED_SCHEMA_VERSION
    with closing(sqlite3.connect(store_path())) as connection:
        names = connection.execute("SELECT name FROM members ORDER BY name").fetchall()
        checkouts = connection.execute(
            "SELECT member_id, machines.name FROM checkouts "
            "JOIN machines USING (machine_id) ORDER BY member_id"
        ).fetchall()
    assert names == [("one-name",), ("two-name",)]
    assert checkouts == [("one", "local"), ("two", "local")]
    assert _installed_record() == VERSION
    assert [path.name for path in _backups()] == [NOW.strftime("%Y%m%dT%H%M%S")]


def test_a_listed_member_with_no_checkout_fails_the_read_back_and_restores(
    old_live: FakeSteps,
) -> None:
    old_live.stub_projects[1].pop("projectPath")  # naming makes no checkout for it

    with pytest.raises(update_live.UpdateError, match="no checkout on local"):
        update_live.update(VERSION, PREVIOUS, old_live.steps(), NOW)

    assert _version(store_path()) == SCHEMA_ELEVEN
    assert old_live.installed == [
        update_live.install_spec(VERSION),
        update_live.restore_spec(PREVIOUS),
    ]
    assert _installed_record() == PREVIOUS


def test_a_member_with_no_name_fails_the_read_back(old_live: FakeSteps) -> None:
    def migrate_without_naming() -> None:
        open_local_store(store_path()).close()  # migrates; only the state opener names

    steps = update_live.Steps(
        install=old_live.installed.append,
        migrate=migrate_without_naming,
        cf_projects=set,
        list_tools=lambda: ALL_TOOLS,
        status=fake_status,
    )

    with pytest.raises(update_live.UpdateError, match="2 members have no name"):
        update_live.update(VERSION, PREVIOUS, steps, NOW)

    assert _version(store_path()) == SCHEMA_ELEVEN


def test_a_cf_projects_that_raises_restores_the_same_way(old_live: FakeSteps) -> None:
    def cf_down() -> set[str]:
        raise update_live.UpdateError("cf could not list its projects: down")

    steps = update_live.Steps(
        install=old_live.installed.append,
        migrate=old_live._migrate,  # pyright: ignore[reportPrivateUsage]
        cf_projects=cf_down,
        list_tools=lambda: ALL_TOOLS,
        status=fake_status,
    )

    with pytest.raises(update_live.UpdateError, match="cf could not list"):
        update_live.update(VERSION, PREVIOUS, steps, NOW)

    assert _version(store_path()) == SCHEMA_ELEVEN
    assert old_live.installed[-1] == update_live.restore_spec(PREVIOUS)
    assert _installed_record() == PREVIOUS


def test_a_list_tools_that_raises_restores_the_same_way(old_live: FakeSteps) -> None:
    def server_down() -> set[str]:
        raise TimeoutError("the MCP server did not answer")

    steps = update_live.Steps(
        install=old_live.installed.append,
        migrate=old_live._migrate,  # pyright: ignore[reportPrivateUsage]
        cf_projects=lambda: old_live.cf_ids,
        list_tools=server_down,
        status=fake_status,
    )

    with pytest.raises(update_live.UpdateError, match="TimeoutError"):
        update_live.update(VERSION, PREVIOUS, steps, NOW)

    assert _version(store_path()) == SCHEMA_ELEVEN
    assert old_live.installed[-1] == update_live.restore_spec(PREVIOUS)


def _failing_migrate() -> None:
    raise subprocess.CalledProcessError(3, ["amoeba", "list"])


def test_a_failed_amoeba_list_restores_the_store_config_and_version_then_a_rerun_works(
    old_live: FakeSteps,
) -> None:
    config_before = config_path().read_text(encoding="utf-8")
    broken = update_live.Steps(
        install=old_live.installed.append,
        migrate=_failing_migrate,
        cf_projects=lambda: old_live.cf_ids,
        list_tools=lambda: ALL_TOOLS,
        status=fake_status,
    )

    with pytest.raises(update_live.UpdateError, match="CalledProcessError") as raised:
        update_live.update(VERSION, PREVIOUS, broken, NOW)

    assert PREVIOUS in str(raised.value)
    assert _version(store_path()) == SCHEMA_ELEVEN
    assert config_path().read_text(encoding="utf-8") == config_before
    assert old_live.installed[-1] == update_live.restore_spec(PREVIOUS)
    assert _installed_record() == PREVIOUS

    update_live.update(VERSION, PREVIOUS, old_live.steps(), LATER)

    assert _version(store_path()) == EXPECTED_SCHEMA_VERSION
    assert _installed_record() == VERSION
    restored = update_live.restore(update_live.newest_backup(), old_live.steps())
    assert restored == PREVIOUS
    assert _version(store_path()) == SCHEMA_ELEVEN
    assert _installed_record() == PREVIOUS


def test_a_killed_update_after_the_migration_keeps_its_backup_on_the_rerun(
    old_live: FakeSteps,
) -> None:
    """#45: the process dies after the migration. The rerun must not back up the
    migrated store and then delete the only backup the old code can read."""

    def migrate_then_die() -> None:
        old_live._migrate()  # pyright: ignore[reportPrivateUsage]
        raise KeyboardInterrupt

    killed = update_live.Steps(
        install=old_live.installed.append,
        migrate=migrate_then_die,
        cf_projects=lambda: old_live.cf_ids,
        list_tools=lambda: ALL_TOOLS,
        status=fake_status,
    )

    with pytest.raises(KeyboardInterrupt):
        update_live.update(VERSION, PREVIOUS, killed, NOW)

    assert _version(store_path()) == EXPECTED_SCHEMA_VERSION
    (first,) = _backups()
    assert _installed_record() == PREVIOUS

    update_live.update(VERSION, PREVIOUS, old_live.steps(), LATER)

    assert _backups() == [first], "the rerun took no second backup"
    assert _version(first / update_live.STORE_BACKUP) == SCHEMA_ELEVEN
    assert _installed_record() == VERSION
    restored = update_live.restore(first, old_live.steps())
    assert restored == PREVIOUS
    assert _version(store_path()) == SCHEMA_ELEVEN
    assert old_live.installed[-1] == update_live.restore_spec(PREVIOUS)


def test_a_rerun_after_a_kill_before_the_migration_takes_a_new_backup(
    old_live: FakeSteps,
) -> None:
    def die_before_migrating() -> None:
        raise KeyboardInterrupt

    killed = update_live.Steps(
        install=old_live.installed.append,
        migrate=die_before_migrating,
        cf_projects=lambda: old_live.cf_ids,
        list_tools=lambda: ALL_TOOLS,
        status=fake_status,
    )
    with pytest.raises(KeyboardInterrupt):
        update_live.update(VERSION, PREVIOUS, killed, NOW)
    assert _version(store_path()) == SCHEMA_ELEVEN
    (first,) = _backups()

    update_live.update(VERSION, PREVIOUS, old_live.steps(), LATER)

    (only,) = _backups()
    assert only != first, "a new backup was taken, as before"
    assert only.name == LATER.strftime("%Y%m%dT%H%M%S")
    assert _version(only / update_live.STORE_BACKUP) == SCHEMA_ELEVEN


def test_a_later_release_takes_its_own_backup_not_the_kept_one(
    old_live: FakeSteps,
) -> None:
    """After a finished update the kept backup records the version before it; a later
    update's previous is the version just installed, so it matches nothing."""
    update_live.update(VERSION, PREVIOUS, old_live.steps(), NOW)

    update_live.update("0.2.9", VERSION, old_live.steps(), LATER)

    (only,) = _backups()
    assert only.name == LATER.strftime("%Y%m%dT%H%M%S")
    assert _version(only / update_live.STORE_BACKUP) == EXPECTED_SCHEMA_VERSION


def test_main_returns_1_and_says_what_failed_and_which_version_was_restored(
    old_live: FakeSteps,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def nothing_installs(_spec: str) -> None:
        raise AssertionError("main must go through PRODUCTION, which is patched")

    monkeypatch.setattr(update_live, "_uv_install", nothing_installs)
    broken = update_live.Steps(
        install=old_live.installed.append,
        migrate=_failing_migrate,
        cf_projects=lambda: old_live.cf_ids,
        list_tools=lambda: ALL_TOOLS,
        status=fake_status,
    )
    monkeypatch.setattr(update_live, "PRODUCTION", broken)
    monkeypatch.setattr(update_live, "check_checkout", lambda: VERSION)
    monkeypatch.setattr(update_live, "installed_version", lambda: VERSION)
    monkeypatch.setattr(update_live, "running_servers", list)

    code = update_live.main(["update"])

    captured = capsys.readouterr()
    assert code == 1
    assert "CalledProcessError" in captured.err
    assert f"restored {PREVIOUS}" in captured.err
    assert old_live.installed[-1] == update_live.restore_spec(PREVIOUS)


def test_the_previous_version_is_the_recorded_one_before_the_installed_one(
    old_live: FakeSteps, monkeypatch: pytest.MonkeyPatch
) -> None:
    """After a kill the installed tool is the new version; the record still names the
    old one, so the rerun's previous matches the backup that kill left."""
    seen: list[str] = []

    def fake_update(
        version: str, previous: str, steps: object, now: datetime
    ) -> list[str]:
        seen.append(previous)
        return []

    monkeypatch.setattr(update_live, "update", fake_update)
    monkeypatch.setattr(update_live, "check_checkout", lambda: VERSION)
    monkeypatch.setattr(update_live, "installed_version", lambda: VERSION)
    monkeypatch.setattr(update_live, "running_servers", list)

    assert update_live.main(["update"]) == 0
    assert update_live.main(["update", "--previous", "0.0.1"]) == 0

    assert seen == [PREVIOUS, "0.0.1"]


def test_restore_checks_the_backup_before_overwriting_the_live_store(
    old_live: FakeSteps,
) -> None:
    update_live.update(VERSION, PREVIOUS, old_live.steps(), NOW)
    backup = update_live.newest_backup()
    live_before = store_path().read_bytes()
    config_before = config_path().read_bytes()
    (backup / update_live.STORE_BACKUP).write_bytes(b"not a database at all" * 100)

    with pytest.raises(update_live.UpdateError, match="nothing restored"):
        update_live.restore(backup, old_live.steps())

    assert store_path().read_bytes() == live_before
    assert config_path().read_bytes() == config_before
    assert old_live.installed[-1] == update_live.install_spec(VERSION)


def test_restore_refuses_a_backup_missing_a_file_and_changes_nothing(
    old_live: FakeSteps,
) -> None:
    update_live.update(VERSION, PREVIOUS, old_live.steps(), NOW)
    backup = update_live.newest_backup()
    (backup / update_live.PREVIOUS_VERSION).unlink()
    live_before = store_path().read_bytes()

    with pytest.raises(update_live.UpdateError, match="has no previous-version"):
        update_live.restore(backup, old_live.steps())

    assert store_path().read_bytes() == live_before


def test_a_failed_read_back_logs_the_traceback(
    old_live: FakeSteps, caplog: pytest.LogCaptureFixture
) -> None:
    broken = update_live.Steps(
        install=old_live.installed.append,
        migrate=_failing_migrate,
        cf_projects=lambda: old_live.cf_ids,
        list_tools=lambda: ALL_TOOLS,
        status=fake_status,
    )

    with pytest.raises(update_live.UpdateError):
        update_live.update(VERSION, PREVIOUS, broken, NOW)

    (record,) = [r for r in caplog.records if r.exc_info is not None]
    assert record.exc_info is not None
    assert record.exc_info[0] is subprocess.CalledProcessError


def test_a_failed_install_puts_the_config_back_and_the_store_is_untouched(
    old_live: FakeSteps,
) -> None:
    _drop_key("prune_after_days")
    config_before = config_path().read_bytes()
    store_before = store_path().read_bytes()

    def install_fails(_spec: str) -> None:
        raise update_live.UpdateError("uv could not install: exit 1")

    steps = update_live.Steps(
        install=install_fails,
        migrate=old_live._migrate,  # pyright: ignore[reportPrivateUsage]
        cf_projects=lambda: old_live.cf_ids,
        list_tools=lambda: ALL_TOOLS,
        status=fake_status,
    )

    with pytest.raises(update_live.UpdateError, match="uv could not install"):
        update_live.update(VERSION, PREVIOUS, steps, NOW)

    assert config_path().read_bytes() == config_before, "the added key is undone"
    assert store_path().read_bytes() == store_before
    assert old_live.migrations == 0


def test_a_backup_killed_mid_copy_leaves_nothing_that_blocks_the_next_update(
    old_live: FakeSteps, monkeypatch: pytest.MonkeyPatch
) -> None:
    def die_copying(_source: Path, _destination: Path) -> None:
        raise KeyboardInterrupt

    with monkeypatch.context() as patch:
        patch.setattr(update_live, "copy_database", die_copying)
        with pytest.raises(KeyboardInterrupt):
            update_live.update(VERSION, PREVIOUS, old_live.steps(), NOW)

    assert _backups() == [], "an unfinished copy is not a backup"
    assert old_live.installed == []

    update_live.update(VERSION, PREVIOUS, old_live.steps(), NOW)

    (only,) = _backups()
    assert only.name == NOW.strftime("%Y%m%dT%H%M%S")
    assert _version(only / update_live.STORE_BACKUP) == SCHEMA_ELEVEN
    leftovers = [p.name for p in update_live.backups_root().iterdir() if p.is_dir()]
    assert leftovers == [only.name], "the success cleanup removed the partial one"


def test_a_backup_from_before_the_version_record_is_not_reused(live: Path) -> None:
    """An older script recorded ``previous-commit``, not ``previous-version``: that
    backup is no restore point for a version, so the update takes its own, not a
    traceback (found on the live state at the 0.2.9 update)."""
    old = update_live.backups_root() / "20261122T000000"
    old.mkdir(parents=True)
    (old / update_live.STORE_BACKUP).write_bytes(b"")
    (old / "previous-commit").write_text("abc\n", encoding="utf-8")

    assert update_live.reusable_backup(PREVIOUS) is None


def test_tool_command_is_the_uv_tool_bin_not_the_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Under ``uv run`` a bare ``amoeba`` is the checkout's; the read-back must use the
    tool install's (found at the 0.2.9 update, where it would have tested the
    checkout)."""
    (tmp_path / "amoeba").write_text("", encoding="utf-8")

    def uv_tool_dir(
        command: list[str], **_: object
    ) -> subprocess.CompletedProcess[str]:
        assert command == ["uv", "tool", "dir", "--bin"]
        return subprocess.CompletedProcess(command, 0, stdout=f"{tmp_path}\n")

    monkeypatch.setattr(update_live.subprocess, "run", uv_tool_dir)

    assert update_live.tool_command("amoeba") == str(tmp_path / "amoeba")
    with pytest.raises(update_live.UpdateError, match="does not exist"):
        update_live.tool_command("amoeba-mcp")


# --- the live store at schema 12: the machine on questions and wakes (262 D14) ---


def _machines_of(table: str) -> list[object]:
    with closing(sqlite3.connect(store_path())) as connection:
        return [
            row[0]
            for row in connection.execute(
                f"SELECT machines.name FROM {table} "  # noqa: S608 - fixed names
                "LEFT JOIN machines USING (machine_id)"
            )
        ]


def test_update_and_restore_against_a_copy_of_a_schema_twelve_store(
    amoeba_home: Path,
) -> None:
    build_schema_12_store(store_path())
    config_path().write_text(example_config_text(), encoding="utf-8")
    fake = FakeSteps()

    update_live.update(VERSION, PREVIOUS, fake.steps(), NOW)

    assert _version(store_path()) == EXPECTED_SCHEMA_VERSION
    assert _machines_of("questions") == ["local"] * QUESTION_COUNT
    assert _machines_of("wakes") == ["local"] * WAKE_COUNT
    with closing(sqlite3.connect(store_path())) as connection:
        connection.execute("UPDATE questions SET question = 'written since'")
        connection.commit()

    restored = update_live.restore(update_live.newest_backup(), fake.steps())

    assert restored == PREVIOUS
    assert _version(store_path()) == SCHEMA_TWELVE
    with closing(sqlite3.connect(store_path())) as connection:
        questions = connection.execute("SELECT question FROM questions").fetchall()
    assert ("written since",) not in questions


class _LosesAMachine(FakeSteps):
    """``amoeba list`` that leaves one question with no machine."""

    def _migrate(self) -> None:
        super()._migrate()
        with closing(sqlite3.connect(store_path())) as connection:
            connection.execute(
                "UPDATE questions SET machine_id = NULL WHERE run_id = 'run-0'"
            )
            connection.commit()


def test_a_question_left_with_no_machine_fails_the_read_back_and_restores(
    amoeba_home: Path,
) -> None:
    build_schema_12_store(store_path())
    config_path().write_text(example_config_text(), encoding="utf-8")

    with pytest.raises(update_live.UpdateError, match="no machine"):
        update_live.update(VERSION, PREVIOUS, _LosesAMachine().steps(), NOW)

    assert _version(store_path()) == SCHEMA_TWELVE
