"""Inject a failure into one store statement, to test that a transaction rolls back."""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence

import pytest

from amoeba.store import Store


class InjectedFailureError(RuntimeError):
    """Raised in place of a statement the test chose to fail."""


def fail_on_statement(
    monkeypatch: pytest.MonkeyPatch, store: Store, statement: str
) -> None:
    """Make ``store`` raise :class:`InjectedFailureError` when it runs ``statement``.

    Patches the store's ``_execute`` for this instance only, so the statements
    before the target one run and are rolled back with the open transaction.
    """
    real_execute = store._execute  # pyright: ignore[reportPrivateUsage]

    def execute(sql_text: str, parameters: Sequence[object]) -> sqlite3.Cursor:
        if sql_text == statement:
            raise InjectedFailureError(statement.strip().split(maxsplit=1)[0])
        return real_execute(sql_text, parameters)

    monkeypatch.setattr(store, "_execute", execute)
