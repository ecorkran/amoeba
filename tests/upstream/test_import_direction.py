"""Dependency direction: upstream adapters sit between the store vocabulary and
the callers, never above the inbox, the process, or the ``Store`` itself."""

from __future__ import annotations

import ast
from pathlib import Path

SRC = Path(__file__).parents[2] / "src" / "amoeba"
FORBIDDEN_FOR_UPSTREAM = ("amoeba.inbox", "amoeba.process", "amoeba.store.store")


def _imported_names(path: Path) -> set[str]:
    """Every module path and every ``module.name`` an import statement mentions."""
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
            names.update(f"{node.module}.{alias.name}" for alias in node.names)
    return names


def _sources(directory: str) -> list[Path]:
    files = sorted((SRC / directory).rglob("*.py"))
    assert files, f"no source files under {directory}"
    return files


def _mentions(names: set[str], prefix: str) -> bool:
    return any(name == prefix or name.startswith(prefix + ".") for name in names)


def test_upstream_does_not_import_the_inbox_the_process_or_the_store_class() -> None:
    for path in _sources("upstream"):
        names = _imported_names(path)
        for forbidden in FORBIDDEN_FOR_UPSTREAM:
            assert not _mentions(names, forbidden), f"{path.name} imports {forbidden}"
        assert not any(name.rsplit(".", 1)[-1] == "Store" for name in names), path.name


def test_the_store_does_not_import_upstream() -> None:
    for path in _sources("store"):
        assert not _mentions(_imported_names(path), "amoeba.upstream"), path.name
