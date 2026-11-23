"""Update the installed amoeba to the release just made and migrate the live store.

Run from the checkout, on its target branch, as the release skill's last step
(`.claude/skills/release/SKILL.md`), once PyPI shows the version, not after a slice
merges:

    uv run python scripts/update_live.py update [--previous VERSION]
    uv run python scripts/update_live.py restore

``update`` backs up the store and config, appends any config key the new code
requires (value from the starter config Amoeba ships), installs the checkout's
version from PyPI with ``uv tool install`` (never a build of the checkout), runs
``amoeba list`` (which migrates the store and names the members) and reads the result
back (the schema version, integrity, foreign keys, the member count, that ``owners``
holds its one row and ``machines`` the one ``local`` row, that no member lacks a name
and every active member ``cf`` lists has a checkout here, and the MCP tool list).
Anything that fails after the install, a failed ``amoeba list`` included, restores
automatically: the store, the config and the previous version, and exits 1 saying what
failed. ``restore`` checks the newest backup is whole, then puts it back and
reinstalls the version that was installed before it. Everything written to the store or
the config after the backup was taken is lost by a restore, automatic or not.

Backups live in ``<state home>/backups/<stamp>/``; a successful update deletes
every older one, so one set is kept, and records the version it installed in
``<state home>/backups/installed-version`` last. Each backup records the version
installed before the update: ``--previous``, else the recorded version, else what
``amoeba --version`` reports. An ``update`` killed after the migration leaves the store
migrated and the record unchanged; ``update`` again then finds that the newest backup
records the version it is about to record as previous and holds an older schema than the
live store, so it keeps that backup as its restore point and takes no new one (#45).
Paths honour ``AMOEBA_HOME`` exactly as amoeba does.
"""

from __future__ import annotations

import argparse
import logging
import os
import shutil
import sqlite3
import subprocess
import sys
import tomllib
from collections.abc import Callable
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import anyio
from mcp import ClientSession, StdioServerParameters, stdio_client

from amoeba.config.home import config_path, state_home, store_path
from amoeba.config.starter import fill_missing_keys, starter_values
from amoeba.config.user_config import ConfigError
from amoeba.operations.names import OperationName
from amoeba.store import sql
from amoeba.store.machines import LOCAL_MACHINE_NAME
from amoeba.store.migrations import EXPECTED_SCHEMA_VERSION
from amoeba.store.store import BUSY_TIMEOUT_SECONDS
from amoeba.upstream.context_forge.cli_call import CfCallFailed
from amoeba.upstream.context_forge.projects import project_details

logger = logging.getLogger("update_live")
CHECKOUT = Path(__file__).resolve().parents[1]
PACKAGE_NAME = "amoeba-ai"
BACKUPS_DIRNAME = "backups"
STORE_BACKUP = "amoeba.sqlite3"
CONFIG_BACKUP = "config.yaml"
PREVIOUS_VERSION = "previous-version"
#: The version the last successful update (or restore) left installed, written last.
INSTALLED_VERSION_RECORD = "installed-version"
#: A backup still being copied is under this prefix; no lookup reads such a directory.
PARTIAL_PREFIX = "."
MCP_LIST_TIMEOUT_SECONDS = 30
INTEGRITY_OK = "ok"
SELECT_OWNER_COUNT = "SELECT count(*) FROM owners"
SELECT_MACHINE_NAMES = "SELECT name FROM machines ORDER BY name"


class UpdateError(Exception):
    """The update cannot go on; the message says why and what was done."""


@dataclass(frozen=True)
class Steps:
    """The side effects ``update`` and ``restore`` call; tests replace them."""

    install: Callable[[str], None]
    migrate: Callable[[], None]
    #: The ids of the projects ``cf`` lists with a path; raises when ``cf`` fails.
    cf_projects: Callable[[], set[str]]
    list_tools: Callable[[], set[str]]


def backups_root() -> Path:
    return state_home() / BACKUPS_DIRNAME


def _git(*args: str) -> str:
    done = subprocess.run(
        ["git", "-C", str(CHECKOUT), *args], capture_output=True, text=True, check=True
    )
    return done.stdout.strip()


def check_checkout() -> str:
    """The checkout's version, once it is on its target and clean."""
    configured = subprocess.run(
        ["cf", "config", "get", "git.integration_branch", "--value"],
        cwd=CHECKOUT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    target = configured or "main"
    branch = _git("rev-parse", "--abbrev-ref", "HEAD")
    if branch != target:
        raise UpdateError(f"checkout is on {branch!r}, not the target {target!r}")
    if _git("status", "--porcelain"):
        raise UpdateError("checkout has uncommitted changes")
    pyproject = tomllib.loads((CHECKOUT / "pyproject.toml").read_text("utf-8"))
    return str(pyproject["project"]["version"])


def example_values() -> dict[str, Any]:
    """The starter config's values: what a key the live config lacks is filled from."""
    return starter_values()


def add_missing_keys(path: Path, examples: dict[str, Any]) -> list[str]:
    """Append each required key the config lacks; returns the keys added."""
    try:
        return fill_missing_keys(path, examples)
    except ConfigError as error:
        raise UpdateError(f"config cannot be completed: {error}") from error


def _connect_read_only(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


def _read_only(path: Path) -> closing[sqlite3.Connection]:
    """A read-only connection that is closed on leaving the ``with`` (a bare
    ``with connection`` only ends a transaction and leaves it open)."""
    return closing(_connect_read_only(path))


def member_count(path: Path) -> int:
    with _read_only(path) as connection:
        row = connection.execute(
            f"SELECT count(*) FROM members WHERE {sql.ACTIVE_MEMBER}"
        ).fetchone()
    return int(row[0])


def copy_database(source_path: Path, destination_path: Path) -> None:
    """Copy one SQLite database onto another through SQLite's backup API.

    The API takes SQLite's own locks, so it is safe while running servers hold
    the store open (a plain file copy over a WAL database corrupts it), and
    their connections see the copied content afterwards.
    """
    source = _connect_read_only(source_path)
    destination = sqlite3.connect(destination_path, timeout=BUSY_TIMEOUT_SECONDS)
    try:
        source.backup(destination)
    finally:
        source.close()
        destination.close()


def take_backup(previous: str, now: datetime) -> Path:
    """Copy the store (SQLite backup, safe with readers) and config; return the dir."""
    stamp = now.strftime("%Y%m%dT%H%M%S")
    target = backups_root() / stamp
    # Built under a name no backup lookup reads and renamed whole, so a copy that fails
    # or is killed leaves nothing a later update mistakes for a backup; the leftover is
    # cleared here, and by a successful update's cleanup.
    partial = backups_root() / f"{PARTIAL_PREFIX}{stamp}"
    if partial.exists():
        shutil.rmtree(partial)
    partial.mkdir(parents=True)
    copy_database(store_path(), partial / STORE_BACKUP)
    shutil.copy2(config_path(), partial / CONFIG_BACKUP)
    (partial / PREVIOUS_VERSION).write_text(previous + "\n", encoding="utf-8")
    partial.rename(target)
    return target


def check_store(expected_members: int, cf_projects: set[str]) -> list[str]:
    """Every read-back failure of the live store; empty when all pass."""
    failures: list[str] = []
    with _read_only(store_path()) as connection:
        version = connection.execute(
            sql.SELECT_SCHEMA_VERSION, (sql.SCHEMA_META_ROW_ID,)
        ).fetchone()
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        dangling = connection.execute("PRAGMA foreign_key_check").fetchall()
        owners = connection.execute(SELECT_OWNER_COUNT).fetchone()[0]
        machines = [row[0] for row in connection.execute(SELECT_MACHINE_NAMES)]
        unnamed = connection.execute(sql.SELECT_UNNAMED_MEMBERS).fetchall()
        no_checkout = {
            row[0]
            for row in connection.execute(
                sql.SELECT_ACTIVE_MEMBERS_WITHOUT_CHECKOUT_ON, (LOCAL_MACHINE_NAME,)
            )
        }
    if version is None or version[0] != EXPECTED_SCHEMA_VERSION:
        failures.append(f"schema version {version} != {EXPECTED_SCHEMA_VERSION}")
    if integrity != INTEGRITY_OK:
        failures.append(f"integrity_check: {integrity}")
    if dangling:
        failures.append(f"foreign_key_check: {len(dangling)} dangling")
    if owners != 1:
        failures.append(f"owners holds {owners} rows, not 1")
    if machines != [LOCAL_MACHINE_NAME]:
        failures.append(f"machines holds {machines}, not just {LOCAL_MACHINE_NAME!r}")
    members = member_count(store_path())
    if members != expected_members:
        failures.append(f"members {members} != {expected_members} before")
    if unnamed:
        failures.append(f"{len(unnamed)} members have no name")
    missing = sorted(no_checkout & cf_projects)
    if missing:
        failures.append(
            f"listed members with no checkout on {LOCAL_MACHINE_NAME}: {missing}"
        )
    return failures


def install_spec(version: str) -> str:
    """The release or a later one: the install records a floor, never a pin, so a
    later `uv tool upgrade amoeba-ai` still moves it."""
    return f"{PACKAGE_NAME}>={version}"


def restore_spec(version: str) -> str:
    """Exactly the version to go back to: a floor would reinstall the new one."""
    return f"{PACKAGE_NAME}=={version}"


def check_backup(backup: Path) -> str:
    """The previous version ``backup`` records, once the backup is whole: every file
    is there and its store passes ``integrity_check`` with a schema version. Nothing
    live is touched, so a damaged backup stops a restore before it overwrites anything.

    Raises:
        UpdateError: The backup is missing a file or its store is damaged.
    """
    for name in (STORE_BACKUP, CONFIG_BACKUP, PREVIOUS_VERSION):
        if not (backup / name).is_file():
            raise UpdateError(f"backup {backup.name} has no {name}; nothing restored")
    try:
        with _read_only(backup / STORE_BACKUP) as connection:
            integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
            version = connection.execute(
                sql.SELECT_SCHEMA_VERSION, (sql.SCHEMA_META_ROW_ID,)
            ).fetchone()
    except sqlite3.Error as error:
        raise UpdateError(
            f"backup {backup.name} store cannot be read: {error}; nothing restored"
        ) from error
    if integrity != INTEGRITY_OK or version is None:
        raise UpdateError(
            f"backup {backup.name} store is damaged (integrity_check: {integrity}, "
            f"schema version: {version}); nothing restored"
        )
    return (backup / PREVIOUS_VERSION).read_text(encoding="utf-8").strip()


def restore(backup: Path, steps: Steps) -> str:
    """Put ``backup`` back and reinstall its previous version; returns that version.

    The backup is checked first (:func:`check_backup`). Everything recorded in the
    store or the config after the backup was taken is lost: a restore puts the files
    back as they were then.
    """
    previous = check_backup(backup)
    copy_database(backup / STORE_BACKUP, store_path())
    shutil.copy2(backup / CONFIG_BACKUP, config_path())
    steps.install(restore_spec(previous))
    record_installed(previous)
    return previous


def backup_sets() -> list[Path]:
    """The finished backups, oldest first (one still being copied is not one)."""
    return sorted(
        p
        for p in backups_root().iterdir()
        if p.is_dir() and not p.name.startswith(PARTIAL_PREFIX)
    )


def newest_backup() -> Path:
    stamps = backup_sets()
    if not stamps:
        raise UpdateError(f"no backup in {backups_root()}")
    return stamps[-1]


def record_installed(version: str) -> None:
    """Write the version now installed, last, once an update or a restore is done."""
    (backups_root() / INSTALLED_VERSION_RECORD).write_text(
        version + "\n", encoding="utf-8"
    )


def recorded_version() -> str | None:
    """The version the last successful update or restore left installed, if any."""
    record = backups_root() / INSTALLED_VERSION_RECORD
    return record.read_text(encoding="utf-8").strip() if record.exists() else None


def _schema_of(path: Path) -> int:
    with _read_only(path) as connection:
        row = connection.execute(
            sql.SELECT_SCHEMA_VERSION, (sql.SCHEMA_META_ROW_ID,)
        ).fetchone()
    return int(row[0])


def reusable_backup(previous: str) -> Path | None:
    """The newest backup, when an earlier ``update`` migrated the store and never
    finished (#45): it records ``previous`` as the version it was taken before, and its
    store holds an older schema than the live one. ``update`` then keeps it as its
    restore point, since a new backup would hold the migrated store and the cleanup
    that follows a success would delete the only one the old code can read."""
    if not backups_root().exists():
        return None
    stamps = backup_sets()
    if not stamps:
        return None
    newest = stamps[-1]
    record = newest / PREVIOUS_VERSION
    if not record.is_file():
        return None  # taken by a script that recorded a commit, not a version
    recorded = record.read_text(encoding="utf-8").strip()
    if recorded != previous:
        return None
    if _schema_of(newest / STORE_BACKUP) >= _schema_of(store_path()):
        return None
    return newest


def _read_back(expected_members: int, steps: Steps) -> list[str]:
    """Migrate and read the result back; the failures found. Anything this raises is a
    failed read-back too, and the caller restores."""
    steps.migrate()
    failures = check_store(expected_members, steps.cf_projects())
    tools = steps.list_tools()
    wanted = {name.value for name in OperationName}
    if tools != wanted:
        failures.append(f"amoeba-mcp tools differ: {sorted(tools ^ wanted)}")
    return failures


def update(version: str, previous: str, steps: Steps, now: datetime) -> list[str]:
    """Run the update; returns the config keys added. Restores on a failed check, and
    on anything that goes wrong after the install."""
    expected_members = member_count(store_path())
    backup = reusable_backup(previous)
    if backup is None:
        backup = take_backup(previous, now)
    else:
        print(
            f"an earlier update migrated the store and did not finish; keeping "
            f"{backup.name} as the restore point and taking no new backup"
        )
    added = add_missing_keys(config_path(), example_values())
    try:
        steps.install(install_spec(version))
    except Exception:  # noqa: BLE001 - re-raised: the config keys were added above, and
        # an install that failed migrated nothing, so only the config goes back.
        logger.exception("the install failed; putting the config back")
        shutil.copy2(backup / CONFIG_BACKUP, config_path())
        raise
    try:
        failures = _read_back(expected_members, steps)
    except Exception as error:  # noqa: BLE001 - the update's process boundary: whatever
        # the migration or a read-back raises (a failed `amoeba list`, `cf`, the MCP
        # server) must restore before the script reports it; KeyboardInterrupt is not
        # caught, which is the killed update the next run recovers from (#45). The
        # traceback is logged first: the `UpdateError` carries only the message.
        logger.exception("the update failed after the install")
        restored = restore(backup, steps)
        raise UpdateError(
            f"{type(error).__name__} after the install: {error}; restored {restored}"
        ) from error
    if failures:
        restored = restore(backup, steps)
        raise UpdateError(f"read-back failed {failures}; restored {restored}")
    for old in backups_root().iterdir():
        if old.is_dir() and old != backup:
            shutil.rmtree(old)
    record_installed(version)
    return added


def _uv_install(spec: str) -> None:
    # --refresh: right after a release the index can lag a cached listing.
    try:
        subprocess.run(
            ["uv", "tool", "install", "--force", "--reinstall", "--refresh", spec],
            check=True,
        )
    except subprocess.CalledProcessError as error:
        raise UpdateError(
            f"uv could not install {spec} (is it on PyPI yet?): exit {error.returncode}"
        ) from error


def tool_command(name: str) -> str:
    """The path of ``name`` in the ``uv tool`` bin directory: the tool install itself.

    Run from the checkout under ``uv run``, a bare ``amoeba`` resolves to the
    checkout's ``.venv``, so the read-back would test the checkout, not the install.
    """
    done = subprocess.run(
        ["uv", "tool", "dir", "--bin"], capture_output=True, text=True, check=True
    )
    command = Path(done.stdout.strip()) / name
    if not command.exists():
        raise UpdateError(f"{command} does not exist: is amoeba-ai a uv tool install?")
    return str(command)


def installed_version() -> str:
    """The version of the tool install, before any update."""
    done = subprocess.run(
        [tool_command("amoeba"), "--version"],
        capture_output=True,
        text=True,
        check=True,
    )
    return done.stdout.strip()


def _amoeba_list() -> None:
    subprocess.run(
        [tool_command("amoeba"), "list"], check=True, stdout=subprocess.DEVNULL
    )


def _cf_projects() -> set[str]:
    """The ids of the projects ``cf`` lists that have a path, as the naming read."""
    found = project_details(subprocess.run)
    if isinstance(found, CfCallFailed):
        raise UpdateError(f"cf could not list its projects: {found.detail}")
    return {detail.id for detail in found.values() if detail.path is not None}


def _installed_tools() -> set[str]:
    async def run() -> set[str]:
        server = StdioServerParameters(
            command=tool_command("amoeba-mcp"), env=dict(os.environ)
        )
        with anyio.fail_after(MCP_LIST_TIMEOUT_SECONDS):
            async with stdio_client(server) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    return {tool.name for tool in (await session.list_tools()).tools}

    return anyio.run(run)


def running_servers() -> list[str]:
    """One line per running ``amoeba-mcp``: pid and its parent's directory."""
    found = subprocess.run(
        ["pgrep", "-f", "amoeba-mcp"], capture_output=True, text=True, check=False
    ).stdout.split()
    lines: list[str] = []
    for pid in found:
        parent = subprocess.run(
            ["ps", "-o", "ppid=", "-p", pid],
            capture_output=True,
            text=True,
            check=False,
        ).stdout.strip()
        cwd = subprocess.run(
            ["lsof", "-a", "-p", parent, "-d", "cwd", "-Fn"],
            capture_output=True,
            text=True,
            check=False,
        ).stdout
        directory = next((x[1:] for x in cwd.splitlines() if x.startswith("n")), "?")
        lines.append(f"  pid {pid}: session in {directory}")
    return lines


PRODUCTION = Steps(
    install=_uv_install,
    migrate=_amoeba_list,
    cf_projects=_cf_projects,
    list_tools=_installed_tools,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Update the installed amoeba to the release just made."
    )
    sub = parser.add_subparsers(dest="command", required=True)
    up = sub.add_parser("update", help="install the released version and migrate")
    up.add_argument("--previous", help="version to restore to if the update fails")
    sub.add_parser("restore", help="put the newest backup back")
    args = parser.parse_args(argv)
    logging.basicConfig(format="%(message)s")
    try:
        if args.command == "update":
            version = check_checkout()
            previous = args.previous or recorded_version() or installed_version()
            added = update(version, previous, PRODUCTION, datetime.now(UTC))
            print(f"updated to {version}; config keys added: {added or 'none'}")
        else:
            backup = newest_backup()
            print(f"restored {backup.name}; reinstalled {restore(backup, PRODUCTION)}")
    except UpdateError as error:
        print(f"update_live: {error}", file=sys.stderr)
        return 1
    servers = running_servers()
    if servers:
        print("These amoeba-mcp servers run the old code; restart their sessions:")
        print("\n".join(servers))
    return 0


if __name__ == "__main__":
    sys.exit(main())
