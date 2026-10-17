"""The projected CF field lists and file name are spelled once, in projects_file.py."""

from __future__ import annotations

import ast
from pathlib import Path

from amoeba.upstream.context_forge import projects_file

PACKAGE = Path(projects_file.__file__).parent
DEFINING_FILE = Path(projects_file.__file__)
SPELLED_ONCE = {
    *projects_file.PROJECT_FIELDS,
    *projects_file.WORKTREE_FIELDS,
    projects_file.PROJECTS_FILE_NAME,
}


def _string_constants(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docstrings = {
        id(node.body[0].value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef)
        and node.body
        and isinstance(node.body[0], ast.Expr)
    }
    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in docstrings
    ]


def test_the_field_tuples_are_not_empty_and_have_no_repeats() -> None:
    assert "developmentPhase" in projects_file.PROJECT_FIELDS
    assert "activeSlice" in projects_file.WORKTREE_FIELDS
    for fields in (projects_file.PROJECT_FIELDS, projects_file.WORKTREE_FIELDS):
        assert len(set(fields)) == len(fields)
    assert "updatedAt" not in SPELLED_ONCE


def test_no_other_module_in_the_package_spells_a_projected_field() -> None:
    others = [p for p in sorted(PACKAGE.glob("*.py")) if p != DEFINING_FILE]
    assert others
    for path in others:
        clashes = SPELLED_ONCE.intersection(_string_constants(path))
        assert not clashes, f"{path.name} spells {sorted(clashes)}"
