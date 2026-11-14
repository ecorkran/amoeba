"""Only the member and pair constants in ``store/sql.py`` query ``members`` (228 D8).

"A removed member is not a member" is written once, as ``sql.ACTIVE_MEMBER``. This
scan keeps it that way: no SQL string in ``src/amoeba`` may name the ``members`` table
except the member and pair statements below and the ``decisions`` join, which must keep
seeing removed members because their answers are the record.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from amoeba.store import sql

SRC = Path(__file__).parents[2] / "src" / "amoeba"
SQL_MODULE = SRC / "store" / "sql.py"

#: Matches a statement that reads or writes the ``members`` table.
MEMBERS_TABLE = re.compile(r"\b(FROM|JOIN|INTO|UPDATE)\s+members\b", re.IGNORECASE)

#: Member reads that skip removed members: every one must carry the predicate.
ACTIVE_READS = frozenset(
    {
        "SELECT_MEMBER",
        "SELECT_MEMBERS_OF",
        "SELECT_PAIRS_OF",
        "SELECT_PAIRS_CONSUMED_BY",
        "SELECT_PAIR",
    }
)
#: Statements that name ``members`` and are not active-only reads.
OTHER_MEMBER_STATEMENTS = frozenset(
    {
        "SELECT_MEMBER_ANY",  # a removed member is read on purpose
        "INSERT_MEMBER",
        "UPDATE_MEMBER",
        "REREGISTER_MEMBER",
        "REMOVE_MEMBER",
    }
)
#: The one named exception: the decisions join keeps removed members (D8).
DECISIONS_JOIN = frozenset(
    {
        "_SELECT_DECISIONS",
        "SELECT_DECISIONS_AFTER_SEQ",
        "SELECT_DECISIONS_SINCE",
        "SELECT_SETTLED_SINCE",  # 229: settled questions keep removed members too
    }
)
#: Pair-read helper that holds the sub-select over active members.
PAIR_HELPER = frozenset({"_PAIR_ENDS_ACTIVE"})


def _sql_constants() -> dict[str, str]:
    """Every module-level string of ``sql.py``, private ones included."""
    return {
        name: value
        for name, value in vars(sql).items()
        if isinstance(value, str) and not name.startswith("__")
    }


def _string_literals(source: str) -> list[str]:
    tree = ast.parse(source)
    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    ]


def test_only_the_named_sql_constants_query_members() -> None:
    allowed = ACTIVE_READS | OTHER_MEMBER_STATEMENTS | DECISIONS_JOIN | PAIR_HELPER

    querying = {
        name for name, value in _sql_constants().items() if MEMBERS_TABLE.search(value)
    }

    assert querying <= allowed, (
        f"unexpected SQL on members: {sorted(querying - allowed)}"
    )
    assert ACTIVE_READS <= querying


def test_every_active_read_carries_the_predicate() -> None:
    constants = _sql_constants()

    for name in ACTIVE_READS:
        assert sql.ACTIVE_MEMBER in constants[name], name
    assert sql.ACTIVE_MEMBER not in constants["SELECT_MEMBER_ANY"]


def test_the_predicate_is_written_once() -> None:
    literals = [
        text
        for text in _string_literals(SQL_MODULE.read_text("utf-8"))
        if "removed_at IS NULL" in text
    ]

    assert literals == [sql.ACTIVE_MEMBER]


def test_no_other_module_names_the_members_table_in_sql() -> None:
    offenders = [
        path.relative_to(SRC).as_posix()
        for path in sorted(SRC.rglob("*.py"))
        if path != SQL_MODULE
        and any(
            MEMBERS_TABLE.search(text)
            for text in _string_literals(path.read_text("utf-8"))
        )
    ]

    assert offenders == []


def test_the_scan_catches_a_members_query() -> None:
    source = 'QUERY = "SELECT project_id FROM members WHERE 1"\n'

    assert any(MEMBERS_TABLE.search(text) for text in _string_literals(source))
