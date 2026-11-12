"""Only ``state_move.py`` calls ``Store.open`` (slice 228, D2).

Every entry point opens the store through ``open_state_store``, which moves legacy
state first; a second caller of ``Store.open`` could create an empty state-home
store before the move. The scan walks the parsed source, so a call split across
lines is still found.
"""

from __future__ import annotations

import ast
from pathlib import Path

SRC = Path(__file__).parents[1] / "src" / "amoeba"
OPENER = SRC / "operations" / "state_move.py"


def calls_store_open(source: str) -> bool:
    return any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "open"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "Store"
        for node in ast.walk(ast.parse(source))
    )


def test_no_module_but_state_move_calls_store_open() -> None:
    modules = sorted(path for path in SRC.rglob("*.py") if path != OPENER)
    assert modules, "amoeba has no source"
    for path in modules:
        assert not calls_store_open(path.read_text(encoding="utf-8")), (
            f"{path.relative_to(SRC)} calls Store.open"
        )


def test_state_move_does_call_it() -> None:
    assert calls_store_open(OPENER.read_text(encoding="utf-8"))


def test_the_scan_catches_a_wrapped_call_and_ignores_other_opens() -> None:
    assert calls_store_open("Store.open(\n    path,\n)\n")
    assert not calls_store_open("path.open()\nopen('x')\n")
