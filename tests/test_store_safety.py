"""Mechanical guard: no test may reach for another tool's real directories.

The testing rules require each tier to carry a guard that scans its own files
for the dangerous accessor rather than trusting that nobody wrote one. The
danger here is a test resolving Squadron's real runs directory or Context
Forge's real data directory and operating on live history instead of a
throwaway file.

Amoeba's own store path is not on the list: ``store_path()`` resolves under
``AMOEBA_HOME``, which the autouse fixture in ``conftest.py`` points at a fresh
directory for every test (slice 222, D10), so it can never reach the real home.

The scan is multiline-aware, per the testing rules: a per-line grep is defeated
by a call split across lines, so this walks the parsed AST instead.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).parent

#: Names that resolve Squadron's runs directory or Context Forge's data
#: directory. A test referencing any of them is reaching outside its throwaway
#: directories. They are fixed at import from the real home directory, so a
#: test points a subprocess at a scratch location by setting ``HOME``, never by
#: naming them.
FORBIDDEN_PATH_NAMES = frozenset(
    {
        "DEFAULT_SQ_RUNS_DIR",
        "DEFAULT_CF_DATA_DIR",
    }
)

#: Files exempt from the scan, because testing the resolver is their job.
EXEMPT_FILENAMES = frozenset({"test_paths.py", Path(__file__).name})


def _test_modules() -> list[Path]:
    return sorted(
        path for path in TESTS_DIR.rglob("*.py") if path.name not in EXEMPT_FILENAMES
    )


def _referenced_forbidden_names(source: str) -> set[str]:
    """Return the forbidden names referenced anywhere in ``source``.

    Walks the AST, so a reference survives any amount of line wrapping —
    ``store_path(\n    "demo"\n)`` is caught exactly as the one-line form is.
    Catches bare references, attribute access, and import statements alike.
    """
    tree = ast.parse(source)
    found: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in FORBIDDEN_PATH_NAMES:
            found.add(node.id)
        elif isinstance(node, ast.Attribute) and node.attr in FORBIDDEN_PATH_NAMES:
            found.add(node.attr)
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name in FORBIDDEN_PATH_NAMES:
                    found.add(alias.name)

    return found


def test_scan_finds_a_wrapped_reference() -> None:
    """The scan itself is verified — a wrapped call must not slip past it."""
    wrapped = (
        "from settings import DEFAULT_SQ_RUNS_DIR\n\n"
        "print(\n    DEFAULT_SQ_RUNS_DIR,\n)\n"
    )

    assert _referenced_forbidden_names(wrapped) == {"DEFAULT_SQ_RUNS_DIR"}


@pytest.mark.parametrize("name", ["DEFAULT_SQ_RUNS_DIR", "DEFAULT_CF_DATA_DIR"])
def test_scan_finds_the_runs_and_cf_directory_constants(name: str) -> None:
    """The real Squadron runs and Context Forge directories are off limits too."""
    source = f"from settings import {name}\n\nprint({name})\n"

    assert _referenced_forbidden_names(source) == {name}


def test_scan_ignores_unrelated_source() -> None:
    """The scan does not fire on test code that stays inside tmp_path."""
    benign = 'from pathlib import Path\n\nPath("throwaway.sqlite3").exists()\n'

    assert _referenced_forbidden_names(benign) == set()


@pytest.mark.parametrize("module_path", _test_modules(), ids=lambda path: path.name)
def test_no_test_module_resolves_a_real_tool_directory(module_path: Path) -> None:
    """No test module references Squadron's or Context Forge's real directories."""
    referenced = _referenced_forbidden_names(module_path.read_text(encoding="utf-8"))

    assert not referenced, (
        f"{module_path.name} references {sorted(referenced)}, which resolve a "
        "real tool directory. Tests must operate only on throwaway directories."
    )
