"""Mechanical guard: only the Runner's reconcile creates nodes (slice 123, D10).

Nodes projected from Context Forge's plan are created in exactly one place,
``runner/lifecycle/reconcile.py``, so a second writer cannot create a duplicate
linked node. The scan walks the parsed AST of ``src/amoeba`` rather than grepping,
so a call split across lines is still found.

Not covered: tests and the contract suite's stand-in Runner, which stage fixtures
and live outside ``src/``; and a call through an alias, which an AST walk for the
attribute name cannot see.
"""

from __future__ import annotations

import ast
from pathlib import Path

SOURCE_DIR = Path(__file__).parent.parent / "src" / "amoeba"

#: The method that creates a node.
CREATE_NODE = "create_node"

#: The only module under ``src/amoeba`` permitted to call it.
PERMITTED_MODULE = "runner/lifecycle/reconcile.py"


def _calls_create_node(source: str) -> list[int]:
    """Line numbers of every call to ``<something>.create_node(...)`` in ``source``."""
    return [
        node.lineno
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == CREATE_NODE
    ]


def test_only_reconcile_calls_create_node() -> None:
    offenders = {
        path.relative_to(SOURCE_DIR).as_posix(): lines
        for path in sorted(SOURCE_DIR.rglob("*.py"))
        if (lines := _calls_create_node(path.read_text(encoding="utf-8")))
        and path.relative_to(SOURCE_DIR).as_posix() != PERMITTED_MODULE
    }
    assert offenders == {}, (
        f"create_node called outside {PERMITTED_MODULE}: {offenders}"
    )


def test_reconcile_does_call_create_node() -> None:
    """The guard would pass vacuously if the permitted module stopped creating."""
    source = (SOURCE_DIR / PERMITTED_MODULE).read_text(encoding="utf-8")
    assert _calls_create_node(source)


def test_a_synthetic_caller_is_detected() -> None:
    synthetic = "store.create_node(\n    project_id='p',\n    kind=kind,\n)\n"
    assert _calls_create_node(synthetic) == [1]


def test_a_definition_or_a_mention_is_not_a_call() -> None:
    source = (
        'def create_node(self):\n    """Calls create_node()."""\nx = "create_node"\n'
    )
    assert _calls_create_node(source) == []
