"""The contract proof's import rule (slice 110, D1): public means exported.

Every module under ``tests/contract/`` may import only what a downstream
consumer could: the names in a public root's ``__all__``. The CLI and HTTP are
the other public surfaces and are reached by subprocess and by HTTP, never by
import. A violation is one of three things:

* a submodule of a root (``amoeba.store.paths``);
* a name the root does not list in ``__all__``;
* any other ``amoeba`` module.

Non-``amoeba`` imports (standard library, pytest, httpx, the ``tests`` helpers)
are not this rule's business.

Each root's ``__all__`` is read by importing the root when the rule runs, never
from a copied list, so the rule cannot drift from the surface it polices.
"""

from __future__ import annotations

import ast
import importlib
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

#: The library surfaces a consumer may import (D1).
PUBLIC_ROOTS = frozenset(
    {
        "amoeba.store",
        "amoeba.inbox",
        "amoeba.feed",
        "amoeba.process",
        "amoeba.upstream.squadron",
        "amoeba.upstream.context_forge",
        "amoeba.inspection",
    }
)

_PACKAGE = "amoeba"


class ViolationKind(StrEnum):
    """Which part of the rule an import broke."""

    SUBMODULE = "submodule_of_a_public_root"
    UNEXPORTED_NAME = "name_not_in_all"
    OUTSIDE_ROOTS = "module_outside_the_public_roots"


@dataclass(frozen=True)
class Violation:
    """One offending import: where it is, what it names, and which rule it broke."""

    path: Path
    line: int
    imported: str
    kind: ViolationKind


def import_violations(path: Path) -> list[Violation]:
    """Every import in one source file that breaks the public-import rule."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    violations: list[Violation] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported = [(alias.name, node.lineno) for alias in node.names]
            violations.extend(_module_violations(path, imported))
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            violations.extend(_from_violations(path, node, node.module))
    return sorted(violations, key=lambda violation: violation.line)


def _is_amoeba(module: str) -> bool:
    return module == _PACKAGE or module.startswith(f"{_PACKAGE}.")


def _module_violations(path: Path, imported: list[tuple[str, int]]) -> list[Violation]:
    """``import a.b.c`` forms: the dotted name itself must be a public root."""
    return [
        Violation(path, line, module, _module_kind(module))
        for module, line in imported
        if _is_amoeba(module) and module not in PUBLIC_ROOTS
    ]


def _module_kind(module: str) -> ViolationKind:
    under_a_root = any(module.startswith(f"{root}.") for root in PUBLIC_ROOTS)
    return ViolationKind.SUBMODULE if under_a_root else ViolationKind.OUTSIDE_ROOTS


def _from_violations(path: Path, node: ast.ImportFrom, module: str) -> list[Violation]:
    """``from a.b import c`` forms."""
    if not _is_amoeba(module):
        return []
    if module in PUBLIC_ROOTS:
        exported = set(importlib.import_module(module).__all__)
        return [
            Violation(
                path,
                node.lineno,
                f"{module}.{alias.name}",
                ViolationKind.UNEXPORTED_NAME,
            )
            for alias in node.names
            if alias.name not in exported
        ]
    # ``from amoeba.upstream import squadron`` names a public root through the
    # imported name; anything else is a submodule of a root or outside them.
    return [
        Violation(path, node.lineno, f"{module}.{alias.name}", _module_kind(module))
        for alias in node.names
        if f"{module}.{alias.name}" not in PUBLIC_ROOTS
    ]
