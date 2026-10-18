"""Layering and single-definition rules for the change feed and detection.

Rule 1: the store imports nothing from upstream, the process, or the feed.
Rule 2: the feed follower imports nothing from the process.
Rule 3: no module this slice adds spells a change kind or detection outcome as
a string literal; each names the enum member instead.
"""

from __future__ import annotations

import ast
from pathlib import Path

from amoeba.store.feed_models import ChangeKind, DetectionOutcome

SRC = Path(__file__).parents[1] / "src" / "amoeba"

FORBIDDEN_FOR_STORE = ("amoeba.upstream", "amoeba.process", "amoeba.feed")
FORBIDDEN_FOR_FEED = ("amoeba.process",)

#: Modules held to Rule 3. Each task that creates a module adds it here; a
#: listed module that does not exist fails rather than being skipped.
SINGLE_DEFINITION_MODULES = (
    "store/sql_feed.py",
    "store/mapping_feed.py",
    "store/feed.py",
    "feed/follower.py",
    "cli/feed.py",
    "store/attribution.py",
    "store/review_sources.py",
    "process/review_detection.py",
    "process/review_scan.py",
    "cli/inspect_feed.py",
)

_VOCABULARY = frozenset(member.value for member in (*ChangeKind, *DetectionOutcome))


def _imported_names(path: Path) -> set[str]:
    """Every module path and every ``module.name`` an import statement mentions."""
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
            names.update(f"{node.module}.{alias.name}" for alias in node.names)
    return names


def _mentions(names: set[str], prefix: str) -> bool:
    return any(name == prefix or name.startswith(prefix + ".") for name in names)


def _violations(directory: str, forbidden: tuple[str, ...]) -> list[str]:
    found: list[str] = []
    for path in sorted((SRC / directory).rglob("*.py")):
        names = _imported_names(path)
        found.extend(
            f"{path.name} imports {prefix}"
            for prefix in forbidden
            if _mentions(names, prefix)
        )
    return found


def _string_literals(path: Path) -> set[str]:
    """String constants in a module, excluding bare-expression strings (docstrings)."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docstrings = {
        id(node.value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)
    }
    return {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in docstrings
    }


def test_rule_1_the_store_imports_no_upstream_process_or_feed() -> None:
    assert _violations("store", FORBIDDEN_FOR_STORE) == []


def test_rule_2_the_feed_imports_no_process() -> None:
    # A directory that does not exist yet has no files, so it passes.
    assert _violations("feed", FORBIDDEN_FOR_FEED) == []


def test_rule_3_no_vocabulary_literal_in_this_slices_modules() -> None:
    for relative in SINGLE_DEFINITION_MODULES:
        path = SRC / relative
        assert path.is_file(), f"{relative} is listed but does not exist"
        literals = _string_literals(path) & _VOCABULARY
        assert not literals, f"{relative} spells {sorted(literals)} as literals"
