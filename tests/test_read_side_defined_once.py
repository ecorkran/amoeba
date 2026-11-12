"""The read side's closed vocabularies and its ``sq`` command are spelled once
(slice 224, 6.1)."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Final

from ast_strings import string_constants

SOURCE_ROOT: Final = Path(__file__).parents[1] / "src" / "amoeba"
RUN_LIST_MODULE: Final = SOURCE_ROOT / "upstream" / "squadron" / "run_list.py"

#: Each vocabulary and the one module that defines it.
VOCABULARIES: Final = {
    "PauseClass": SOURCE_ROOT / "operations" / "pause_class.py",
    "UnplacedReason": SOURCE_ROOT / "operations" / "status_models.py",
    "WaitingRunState": SOURCE_ROOT / "operations" / "status_models.py",
    "RejectCode": SOURCE_ROOT / "operations" / "reject_codes.py",
    "MarkReadOutcome": SOURCE_ROOT / "operations" / "mark_read.py",
    "RunFileUnreadable": SOURCE_ROOT / "operations" / "status_models.py",
}


def _classes_named(name: str) -> list[Path]:
    return [
        path
        for path in sorted(SOURCE_ROOT.rglob("*.py"))
        if any(
            isinstance(node, ast.ClassDef) and node.name == name
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        )
    ]


def test_each_closed_vocabulary_is_defined_in_exactly_one_module() -> None:
    for name, home in VOCABULARIES.items():
        assert _classes_named(name) == [home], name


def test_only_run_list_spells_the_runs_list_command() -> None:
    spellers = [
        path
        for path in sorted(SOURCE_ROOT.rglob("*.py"))
        if {"runs", "list"} <= set(string_constants(path))
    ]

    assert spellers == [RUN_LIST_MODULE]
