"""Update the installed amoeba to this checkout and migrate the live store.

Run from the checkout, on its target branch, after a slice merges:

    uv run python scripts/update_live.py update [--previous SHA]
    uv run python scripts/update_live.py restore

``update`` backs up the store and config, appends any config key the new code
requires (value from the config contract's example), installs this checkout with
``uv tool install``, runs ``amoeba list`` (which migrates the store) and reads the
result back. A failed read-back restores automatically. ``restore`` puts the
newest backup back and reinstalls the commit that was installed before it.

Backups live in ``<state home>/backups/<stamp>/``; a successful update deletes
every older one, so one set is kept. ``<state home>/backups/installed-commit``
records what was last installed, and is the next update's restore point.
Paths honour ``AMOEBA_HOME`` exactly as amoeba does.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import sqlite3
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import anyio
import yaml
from mcp import ClientSession, StdioServerParameters, stdio_client

from amoeba.config.home import config_path, state_home, store_path
from amoeba.config.user_config import ConfigError, UserConfig, load_user_config
from amoeba.operations.names import OperationName
from amoeba.store import sql
from amoeba.store.migrations import EXPECTED_SCHEMA_VERSION
from amoeba.store.store import BUSY_TIMEOUT_SECONDS

CHECKOUT = Path(__file__).resolve().parents[1]
CONFIG_CONTRACT = CHECKOUT / "docs" / "config-contract.md"
BACKUPS_DIRNAME = "backups"
STORE_BACKUP = "amoeba.sqlite3"
CONFIG_BACKUP = "config.yaml"
PREVIOUS_COMMIT = "previous-commit"
INSTALLED_COMMIT = "installed-commit"
MCP_LIST_TIMEOUT_SECONDS = 30
INTEGRITY_OK = "ok"


class UpdateError(Exception):
    """The update cannot go on; the message says why and what was done."""


@dataclass(frozen=True)
class Steps:
    """The side effects ``update`` and ``restore`` call; tests replace them."""

    install: Callable[[str], None]
    migrate: Callable[[], None]
    list_tools: Callable[[], set[str]]


def backups_root() -> Path:
    return state_home() / BACKUPS_DIRNAME


def _git(*args: str) -> str:
    done = subprocess.run(
        ["git", "-C", str(CHECKOUT), *args], capture_output=True, text=True, check=True
    )
    return done.stdout.strip()


def check_checkout() -> str:
    """The checkout's HEAD commit, once it is on its target and clean."""
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
    return _git("rev-parse", "HEAD")


def example_values() -> dict[str, Any]:
    """The yaml block under ``## Example`` in the config contract, parsed."""
    text = CONFIG_CONTRACT.read_text(encoding="utf-8").split("## Example", 1)[1]
    match = re.search(r"```yaml\n(.*?)```", text, re.DOTALL)
    if match is None:
        raise UpdateError(f"no yaml block under ## Example in {CONFIG_CONTRACT}")
    values: dict[str, Any] = yaml.safe_load(match.group(1))
    return values


def add_missing_keys(path: Path, examples: dict[str, Any]) -> list[str]:
    """Append each required key the config lacks; returns the keys added."""
    text = path.read_text(encoding="utf-8")
    present: dict[str, Any] = yaml.safe_load(text) or {}
    missing = [key for key in UserConfig.model_fields if key not in present]
    unknown = [key for key in missing if key not in examples]
    if unknown:
        raise UpdateError(f"config lacks {unknown} and the contract has no example")
    if missing:
        addition = yaml.safe_dump(
            {key: examples[key] for key in missing}, sort_keys=False
        )
        separator = "" if text.endswith("\n") else "\n"
        path.write_text(text + separator + addition, encoding="utf-8")
    try:
        load_user_config(path)
    except ConfigError as error:
        raise UpdateError(f"config does not validate: {error}") from error
    return missing


def _read_only(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


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
    source = _read_only(source_path)
    destination = sqlite3.connect(destination_path, timeout=BUSY_TIMEOUT_SECONDS)
    try:
        source.backup(destination)
    finally:
        source.close()
        destination.close()


def take_backup(previous: str, now: datetime) -> Path:
    """Copy the store (SQLite backup, safe with readers) and config; return the dir."""
    target = backups_root() / now.strftime("%Y%m%dT%H%M%S")
    target.mkdir(parents=True)
    copy_database(store_path(), target / STORE_BACKUP)
    shutil.copy2(config_path(), target / CONFIG_BACKUP)
    (target / PREVIOUS_COMMIT).write_text(previous + "\n", encoding="utf-8")
    return target


def check_store(expected_members: int) -> list[str]:
    """Every read-back failure of the live store; empty when all pass."""
    failures: list[str] = []
    with _read_only(store_path()) as connection:
        version = connection.execute(
            sql.SELECT_SCHEMA_VERSION, (sql.SCHEMA_META_ROW_ID,)
        ).fetchone()
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        dangling = connection.execute("PRAGMA foreign_key_check").fetchall()
    if version is None or version[0] != EXPECTED_SCHEMA_VERSION:
        failures.append(f"schema version {version} != {EXPECTED_SCHEMA_VERSION}")
    if integrity != INTEGRITY_OK:
        failures.append(f"integrity_check: {integrity}")
    if dangling:
        failures.append(f"foreign_key_check: {len(dangling)} dangling")
    members = member_count(store_path())
    if members != expected_members:
        failures.append(f"members {members} != {expected_members} before")
    return failures


def install_spec(commit: str) -> str:
    return f"amoeba @ git+file://{CHECKOUT}@{commit}"


def restore(backup: Path, steps: Steps) -> str:
    """Put ``backup`` back and reinstall its previous commit; returns that commit."""
    copy_database(backup / STORE_BACKUP, store_path())
    shutil.copy2(backup / CONFIG_BACKUP, config_path())
    previous = (backup / PREVIOUS_COMMIT).read_text(encoding="utf-8").strip()
    steps.install(install_spec(previous))
    return previous


def newest_backup() -> Path:
    stamps = sorted(p for p in backups_root().iterdir() if p.is_dir())
    if not stamps:
        raise UpdateError(f"no backup in {backups_root()}")
    return stamps[-1]


def previous_commit(given: str | None) -> str:
    """The commit to restore to: ``--previous``, else the last recorded install."""
    if given:
        return given
    record = backups_root() / INSTALLED_COMMIT
    if not record.exists():
        raise UpdateError(
            f"no {record}: pass --previous with the commit the installed amoeba "
            "was built from (right after a merge, `git rev-parse HEAD^1`)"
        )
    return record.read_text(encoding="utf-8").strip()


def update(head: str, previous: str, steps: Steps, now: datetime) -> list[str]:
    """Run the update; returns the config keys added. Restores on a failed check."""
    expected_members = member_count(store_path())
    backup = take_backup(previous, now)
    added = add_missing_keys(config_path(), example_values())
    steps.install(install_spec(head))
    steps.migrate()
    failures = check_store(expected_members)
    tools = steps.list_tools()
    wanted = {name.value for name in OperationName}
    if tools != wanted:
        failures.append(f"amoeba-mcp tools differ: {sorted(tools ^ wanted)}")
    if failures:
        restored = restore(backup, steps)
        raise UpdateError(f"read-back failed {failures}; restored {restored}")
    (backups_root() / INSTALLED_COMMIT).write_text(head + "\n", encoding="utf-8")
    for old in backups_root().iterdir():
        if old.is_dir() and old != backup:
            shutil.rmtree(old)
    return added


def _uv_install(spec: str) -> None:
    subprocess.run(
        ["uv", "tool", "install", "--force", "--reinstall", spec], check=True
    )


def _amoeba_list() -> None:
    subprocess.run(["amoeba", "list"], check=True, stdout=subprocess.DEVNULL)


def _installed_tools() -> set[str]:
    async def run() -> set[str]:
        server = StdioServerParameters(command="amoeba-mcp", env=dict(os.environ))
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
    install=_uv_install, migrate=_amoeba_list, list_tools=_installed_tools
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Update the installed amoeba to this checkout."
    )
    sub = parser.add_subparsers(dest="command", required=True)
    up = sub.add_parser("update", help="install this checkout and migrate")
    up.add_argument("--previous", help="commit to restore to if the update fails")
    sub.add_parser("restore", help="put the newest backup back")
    args = parser.parse_args(argv)
    try:
        if args.command == "update":
            head = check_checkout()
            previous = previous_commit(args.previous)
            added = update(head, previous, PRODUCTION, datetime.now(UTC))
            print(f"updated to {head[:12]}; config keys added: {added or 'none'}")
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
