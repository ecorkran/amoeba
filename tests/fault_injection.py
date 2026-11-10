"""Fail one named SQL statement in a transaction, to prove the block rolls back."""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence

import pytest

from amoeba.store.store import Transaction


class InjectedFailureError(RuntimeError):
    """Raised in place of a statement the test chose to fail."""


def fail_on_statement(
    monkeypatch: pytest.MonkeyPatch,
    transaction: Transaction,
    statement: str,
    error: Exception | None = None,
) -> None:
    """Make ``transaction`` raise ``error`` when it is asked to run ``statement``.

    Patches this transaction only, so the statements before the target run and are
    rolled back with the block. ``error`` defaults to ``InjectedFailureError``.
    """
    real_execute = transaction.execute
    failure = error if error is not None else InjectedFailureError(statement.strip())

    def execute(
        statement_text: str, parameters: Sequence[object] = ()
    ) -> sqlite3.Cursor:
        if statement_text == statement:
            raise failure
        return real_execute(statement_text, parameters)

    monkeypatch.setattr(transaction, "execute", execute)
