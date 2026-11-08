"""Layering: ``amoeba.upstream`` imports nothing from ``amoeba.answering`` (D6).

The library reads as ``answering -> upstream -> stdlib, pydantic, pyyaml``. A shared
piece that both layers need lives in ``upstream``, never the other way round. An import
of a package that no longer exists is not checked here: it fails pyright and the suite.
"""

from __future__ import annotations

import ast
from pathlib import Path

SRC = Path(__file__).parents[1] / "src" / "amoeba"
UPSTREAM = SRC / "upstream"
FORBIDDEN_FOR_UPSTREAM = "amoeba.answering"


def _imported_names(source: str) -> set[str]:
    """Every module path and every ``module.name`` an import statement mentions."""
    names: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
            names.update(f"{node.module}.{alias.name}" for alias in node.names)
    return names


def _mentions(names: set[str], prefix: str) -> bool:
    return any(name == prefix or name.startswith(prefix + ".") for name in names)


def _violations(source: str) -> bool:
    return _mentions(_imported_names(source), FORBIDDEN_FOR_UPSTREAM)


def test_upstream_imports_nothing_from_answering() -> None:
    files = sorted(UPSTREAM.rglob("*.py"))
    assert files, "amoeba.upstream has no source"
    for path in files:
        assert not _violations(path.read_text(encoding="utf-8")), path.name


def test_the_rule_catches_each_way_of_importing_answering() -> None:
    assert _violations("import amoeba.answering.values\n")
    assert _violations("from amoeba.answering import values\n")
    assert _violations("from amoeba.answering.values import DeclineReason\n")


def test_the_rule_ignores_upstream_and_unrelated_imports() -> None:
    assert not _violations("from amoeba.upstream.squadron import launch\n")
    assert not _violations("from amoeba import answering_notes\nimport json\n")
