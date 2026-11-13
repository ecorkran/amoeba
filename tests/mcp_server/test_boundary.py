"""``amoeba.mcp`` holds no operation logic and reaches nothing but ``wiring`` and the
operations' types (slice 226, D10, task 5.3).

It imports none of ``store``, ``config``, ``upstream``, ``answering`` or ``cli``: what
it needs from them (``start_child``, ``LaunchError``, ``LaunchLogs``, the log paths)
comes through ``wiring``. The scan walks the parsed source and resolves relative
imports, so ``from ..store import x`` is caught as ``amoeba.store``.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

SRC = Path(__file__).parents[2] / "src"
MCP_PACKAGE = "amoeba.mcp"
FORBIDDEN = (
    "amoeba.store",
    "amoeba.config",
    "amoeba.upstream",
    "amoeba.answering",
    "amoeba.cli",
)


def _imported_modules(source: str, package: str) -> set[str]:
    """Every absolute module path ``source`` (in ``package``) imports, with the names
    imported from it (``from a import b`` also names ``a.b``)."""
    names: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = package.split(".")[: len(package.split(".")) - node.level + 1]
                module = ".".join([*base, *([node.module] if node.module else [])])
            else:
                module = node.module or ""
            names.add(module)
            names.update(f"{module}.{alias.name}" for alias in node.names)
    return names


def _forbidden_in(source: str, package: str = MCP_PACKAGE) -> list[str]:
    names = _imported_modules(source, package)
    return sorted(
        prefix
        for prefix in FORBIDDEN
        if any(name == prefix or name.startswith(prefix + ".") for name in names)
    )


MCP_FILES = sorted((SRC / "amoeba" / "mcp").glob("*.py"))


def test_there_are_mcp_modules_to_scan() -> None:
    assert {path.name for path in MCP_FILES} >= {
        "tools.py",
        "in_process.py",
        "detached.py",
        "server.py",
    }


@pytest.mark.parametrize("path", MCP_FILES, ids=lambda path: path.name)
def test_no_mcp_module_imports_a_forbidden_package(path: Path) -> None:
    assert _forbidden_in(path.read_text(encoding="utf-8")) == []


@pytest.mark.parametrize(
    "source",
    [
        "import amoeba.store.store\n",
        "from amoeba.config.home import state_layout\n",
        "from amoeba import upstream\n",
        "from amoeba.answering import values\n",
        "from amoeba.cli.main import main\n",
        "from ..store import Store\n",
        "from ..config import home\n",
        "from .. import cli\n",
    ],
)
def test_the_scan_catches_each_way_of_importing(source: str) -> None:
    assert _forbidden_in(source)


def test_the_scan_lets_wiring_and_operations_through() -> None:
    allowed = "from amoeba import wiring\nfrom amoeba.operations.names import Door\n"

    assert _forbidden_in(allowed) == []
