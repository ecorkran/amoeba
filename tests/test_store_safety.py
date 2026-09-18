"""Mechanical guard: no test may reach for the central per-supervisor store.

The testing rules require each tier to carry a guard that scans its own files
for the dangerous accessor rather than trusting that nobody wrote one. The
danger here is a test resolving the real store path and operating on the
supervisor's live lifecycle history instead of a throwaway file.

The scan is multiline-aware, per the testing rules: a per-line grep is defeated
by a call split across lines, so this walks the parsed AST instead.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from amoeba.store import paths

TESTS_DIR = Path(__file__).parent

#: Names defined in ``amoeba.store.paths`` that resolve the central store. A
#: test referencing any of them is reaching outside its throwaway store.
FORBIDDEN_PATH_NAMES = frozenset(
    {
        paths.store_dir.__name__,
        paths.store_path.__name__,
        "DEFAULT_STORE_DIR",
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
        'from amoeba.store.paths import store_path\n\nstore_path(\n    "demo",\n)\n'
    )

    assert _referenced_forbidden_names(wrapped) == {"store_path"}


def test_scan_ignores_unrelated_source() -> None:
    """The scan does not fire on test code that stays inside tmp_path."""
    benign = 'from pathlib import Path\n\nPath("throwaway.sqlite3").exists()\n'

    assert _referenced_forbidden_names(benign) == set()


@pytest.mark.parametrize("module_path", _test_modules(), ids=lambda path: path.name)
def test_no_test_module_resolves_the_central_store(module_path: Path) -> None:
    """No test module references the central store path constant or resolver."""
    referenced = _referenced_forbidden_names(module_path.read_text(encoding="utf-8"))

    assert not referenced, (
        f"{module_path.name} references {sorted(referenced)} from amoeba.store.paths. "
        "Tests must operate only on a throwaway store created by the fixtures in "
        "conftest.py, never on the central per-supervisor store."
    )
