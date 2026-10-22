"""Shared support for tests that journal an ``sq_run`` (slice 120, D1).

``run_id`` is a required parameter key, so every test that journals an
``sq_run`` must carry one. ``sq_run_parameters`` is the one place that adds it.
``insert_legacy_sq_run_entry`` writes the other shape: a row from before slice
120, which has no run id and which ``journal_issue`` would now refuse.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Mapping
from typing import Final

from amoeba.store import sql_journal
from amoeba.store.journal_models import PARAM_RUN_ID

#: The run id a test uses when it does not care which run it is.
TEST_RUN_ID: Final = "run-20261022-test-00000001"


def sq_run_parameters(
    parameters: Mapping[str, object], run_id: str = TEST_RUN_ID
) -> dict[str, object]:
    """Return ``parameters`` with the run id added. Nothing else changes."""
    return {**parameters, PARAM_RUN_ID: run_id}


def insert_legacy_sq_run_entry(
    connection: sqlite3.Connection,
    *,
    entry_id: str,
    project_id: str,
    node_id: str,
    parameters: Mapping[str, object],
    issued_at: str,
) -> None:
    """Write one unresolved pre-120 ``sq_run`` row, as the store once did.

    ``parameters`` is stored as given, so a caller passes no run id. The write
    goes through the store's own insert statement, not ``journal_issue``.
    """
    connection.execute(
        sql_journal.INSERT_JOURNAL_ENTRY,
        (
            entry_id,
            project_id,
            node_id,
            "sq_run",
            json.dumps(dict(parameters)),
            issued_at,
        ),
    )
    connection.commit()
