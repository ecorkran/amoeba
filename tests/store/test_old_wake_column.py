"""Only naming reads and clears the retired ``members.wake_command`` (slice 261, D2).

The column stays because the migration cannot move it. Two statements in
``store/sql.py`` name it (the read of unnamed members and the null-out), and only the
naming modules use them.
"""

from __future__ import annotations

import ast
from pathlib import Path

from amoeba.store import sql

SRC = Path(__file__).parents[2] / "src" / "amoeba"
OLD_COLUMN_STATEMENTS = frozenset(
    {"SELECT_UNNAMED_MEMBERS", "CLEAR_MEMBER_WAKE_COMMAND"}
)
#: The modules allowed to use them: naming, and ``store.member_names`` which holds the
#: functions both call.
ALLOWED_USERS = frozenset(
    {"operations/naming.py", "operations/name_by_id.py", "store/member_names.py"}
)


def test_only_two_member_statements_name_the_old_column() -> None:
    naming = {
        name
        for name, value in vars(sql).items()
        if isinstance(value, str) and "wake_command" in value and "members" in value
    }

    assert naming == OLD_COLUMN_STATEMENTS


def test_only_the_naming_modules_use_the_two_statements() -> None:
    users = {
        path.relative_to(SRC).as_posix()
        for path in SRC.rglob("*.py")
        if path != SRC / "store" / "sql.py"
        and any(
            isinstance(node, ast.Attribute) and node.attr in OLD_COLUMN_STATEMENTS
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        )
    }

    assert users
    assert users <= ALLOWED_USERS
