"""Shared by the ``send``, ``inbox``, ``reply`` and ``cancel`` CLI tests (slice 240).

The recorded ``cf`` answers every lookup with the directory's own project, so a request
sent here is addressed to the sender itself: enough to check text, ``-j`` and exits.
The three-repo scenario has its own routing ``cf``.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from store_open import open_local_store

from amoeba.cli.exit_codes import EXIT_OK
from amoeba.config.home import store_path
from cli.cli_support import (
    PROJECT_ID,
    PROJECT_NAME,
    result_of,
    run_amoeba,
    write_config,
)

__all__ = [
    "PROJECT_ID",
    "PROJECT_NAME",
    "registered",
    "result_of",
    "run_amoeba",
    "send_note",
    "send_request",
    "stored_rows",
]


def registered(tmp_path: Path) -> None:
    """The config written and this checkout registered as a member."""
    write_config()
    assert run_amoeba(tmp_path, "add").returncode == EXIT_OK


def send_request(
    tmp_path: Path, request_id: str, *extra: str, as_json: bool = True
) -> subprocess.CompletedProcess[str]:
    """``amoeba send`` of a request to this checkout's own member."""
    return run_amoeba(
        tmp_path,
        "send",
        "--id",
        request_id,
        "--to",
        PROJECT_NAME,
        "--subject",
        f"subject of {request_id}",
        "--body",
        f"body of {request_id}",
        *extra,
        as_json=as_json,
    )


def send_note(
    tmp_path: Path, note_id: str, *extra: str, as_json: bool = True
) -> subprocess.CompletedProcess[str]:
    """``amoeba send --note`` to this checkout's own member (``--to``), or to whatever
    ``extra`` names."""
    recipient = () if "--to-program" in extra else ("--to", PROJECT_NAME)
    return run_amoeba(
        tmp_path,
        "send",
        "--note",
        "--id",
        note_id,
        *recipient,
        "--subject",
        f"subject of {note_id}",
        "--body",
        f"body of {note_id}",
        *extra,
        as_json=as_json,
    )


def stored_rows(table: str) -> list[tuple[Any, ...]]:
    """Every row of ``table`` in the store the subprocesses used."""
    with open_local_store(store_path()) as store, store.read() as transaction:
        return [tuple(row) for row in transaction.execute(f"SELECT * FROM {table}")]
