"""No test hands its whole environment to a child process.

The testing rules say to pass an explicit list of named variables, never everything:
a child (a stub, the ``amoeba`` command, a model with a shell) can read whatever it
is given. ``live_environment.process_environment`` and ``pipeline_environment`` build
the named lists. The scan walks the parsed source, so a wrapped expression is found.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).parent


def _is_os_environ(node: ast.expr | None) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "environ"
        and isinstance(node.value, ast.Name)
        and node.value.id == "os"
    )


def whole_environment_uses(source: str) -> list[int]:
    """Lines that unpack ``os.environ`` into a dict or pass it as ``env=``."""
    lines: list[int] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Dict):
            lines += [
                value.lineno
                for key, value in zip(node.keys, node.values, strict=True)
                if key is None and _is_os_environ(value)
            ]
        elif isinstance(node, ast.keyword) and node.arg == "env":
            if _is_os_environ(node.value):
                lines.append(node.value.lineno)
    return lines


def test_the_scan_finds_each_way_of_passing_everything() -> None:
    assert whole_environment_uses("e = {**os.environ, 'A': '1'}\n")
    assert whole_environment_uses("run(['x'], env=os.environ)\n")
    assert whole_environment_uses("run(\n    ['x'],\n    env=os.environ,\n)\n")


def test_the_scan_ignores_named_lists_and_plain_reads() -> None:
    assert not whole_environment_uses("e = process_environment(os.environ, A='1')\n")
    assert not whole_environment_uses("x = os.environ['AMOEBA_HOME']\n")
    assert not whole_environment_uses("e = {**named, 'A': '1'}\n")


@pytest.mark.parametrize(
    "module", sorted(TESTS_DIR.rglob("*.py")), ids=lambda path: path.name
)
def test_no_test_module_passes_its_whole_environment_on(module: Path) -> None:
    found = whole_environment_uses(module.read_text(encoding="utf-8"))

    assert not found, (
        f"{module.name}:{found} passes os.environ whole; use "
        "live_environment.process_environment or pipeline_environment"
    )
