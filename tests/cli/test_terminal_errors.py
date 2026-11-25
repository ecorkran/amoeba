"""What a person at a terminal sees when a command fails, against what a hook's log
keeps: the terminal gets the messages, the log gets the traceback too."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from store_open import open_local_store

from amoeba.cli.exit_codes import EXIT_ERROR
from amoeba.config.home import store_path
from cli.cli_support import run_amoeba, write_config

NEWER_SCHEMA_VERSION = 99


def _stamp_the_store_newer() -> None:
    write_config()
    open_local_store(store_path()).close()
    with sqlite3.connect(store_path()) as connection:
        connection.execute(
            "UPDATE schema_meta SET version = ?", (NEWER_SCHEMA_VERSION,)
        )
    connection.close()


def test_a_newer_store_is_two_plain_lines_at_a_terminal(tmp_path: Path) -> None:
    _stamp_the_store_newer()

    completed = run_amoeba(tmp_path, "list", stderr_terminal=True)

    assert completed.returncode == EXIT_ERROR
    where, error = completed.stderr.splitlines()
    assert where == f"cannot open store at {store_path()}"
    assert error.startswith("error: StoreSchemaError: this amoeba is older than")
    assert "Upgrade amoeba-ai" in error


def test_a_newer_store_keeps_its_traceback_in_a_captured_log(tmp_path: Path) -> None:
    _stamp_the_store_newer()

    completed = run_amoeba(tmp_path, "list")

    assert completed.returncode == EXIT_ERROR
    assert "Traceback" in completed.stderr
    assert "error: StoreSchemaError" in completed.stderr
