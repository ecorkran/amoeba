"""The PM's instructions travel one road: the resolution slot, then one argv element.

A source test, in the style of the "spelled once" tests. Only the continuation act
reads the text, and only ``argv.py`` builds the ``--instructions`` element, so the
text cannot leak into a journal parameter, a log line or a payload by another path.
"""

from __future__ import annotations

import ast
from pathlib import Path

from ast_strings import string_constants

from amoeba.runner.resolutions.argv import INSTRUCTIONS_FLAG

RUNNER = Path(__file__).resolve().parents[3] / "src" / "amoeba" / "runner"
READER = RUNNER / "resolutions" / "act.py"
BUILDER = RUNNER / "resolutions" / "argv.py"


def _runner_modules() -> list[Path]:
    return sorted(RUNNER.rglob("*.py"))


def test_only_the_continuation_act_reads_the_instructions_text() -> None:
    readers = [
        path
        for path in _runner_modules()
        if any(
            isinstance(node, ast.Attribute) and node.attr == "instructions"
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        )
    ]

    assert readers == [READER]


def test_only_argv_builds_the_instructions_element() -> None:
    spelled = [
        path
        for path in _runner_modules()
        if INSTRUCTIONS_FLAG in string_constants(path)
    ]

    assert spelled == [BUILDER]
