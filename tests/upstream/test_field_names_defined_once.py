"""Each Squadron key, heading, and tag is spelled once, in ``review_fields.py``."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Final

from amoeba.upstream.squadron import review_fields

PACKAGE = Path(review_fields.__file__).parent
FIELDS_FILE = Path(review_fields.__file__)


def _field_values() -> set[str]:
    return {
        value
        for name, value in vars(review_fields).items()
        if name.isupper() and isinstance(value, str)
    }


def _docstring_nodes(tree: ast.AST) -> set[int]:
    """Ids of the string-constant nodes that are docstrings."""
    ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef):
            body = node.body
            if body and isinstance(body[0], ast.Expr):
                ids.add(id(body[0].value))
    return ids


def _string_constants(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docstrings = _docstring_nodes(tree)
    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in docstrings
    ]


SQUADRON_VALUES: Final = _field_values()


def test_the_field_table_is_not_empty() -> None:
    assert {"verdict", "squadronVersion", "Provider Failure"} <= SQUADRON_VALUES


def test_no_other_module_spells_a_squadron_key_literally() -> None:
    others = [path for path in sorted(PACKAGE.glob("*.py")) if path != FIELDS_FILE]
    assert others
    for path in others:
        clashes = SQUADRON_VALUES.intersection(_string_constants(path))
        assert not clashes, f"{path.name} spells {sorted(clashes)}"
