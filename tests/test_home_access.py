"""``config/home.py`` alone locates the home: no other module reads ``AMOEBA_HOME``.

A second reader of the variable, or a second ``Path.home()``, would be a second
way to choose the location (slice 222, D1 and D10). The scan walks the parsed
source, so a call split across lines is still found.
"""

from __future__ import annotations

import ast
from pathlib import Path

from ast_strings import string_constants

SRC = Path(__file__).parents[1] / "src" / "amoeba"
HOME_MODULE = SRC / "config" / "home.py"
HOME_VARIABLE_NAME = "AMOEBA_HOME"


def _calls_path_home(source: str) -> bool:
    return any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "home"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "Path"
        for node in ast.walk(ast.parse(source))
    )


def _names_the_variable(source: str, tmp: Path) -> bool:
    module = tmp / "module.py"
    module.write_text(source, encoding="utf-8")
    return any(HOME_VARIABLE_NAME in text for text in string_constants(module))


def test_no_other_module_reads_the_variable_or_asks_for_the_users_home() -> None:
    modules = sorted(path for path in SRC.rglob("*.py") if path != HOME_MODULE)
    assert modules, "amoeba has no source"
    for path in modules:
        source = path.read_text(encoding="utf-8")
        assert not _calls_path_home(source), f"{path} calls Path.home"
        assert HOME_VARIABLE_NAME not in "".join(string_constants(path)), (
            f"{path} names {HOME_VARIABLE_NAME}"
        )


def test_the_scan_catches_a_wrapped_path_home_call() -> None:
    assert _calls_path_home("from pathlib import Path\nx = Path.home(\n)\n")
    assert not _calls_path_home("from pathlib import Path\nx = Path('a')\n")


def test_the_scan_catches_the_variable_name(tmp_path: Path) -> None:
    assert _names_the_variable("import os\nos.environ['AMOEBA_HOME']\n", tmp_path)
    assert not _names_the_variable('"""AMOEBA_HOME in a docstring."""\n', tmp_path)
