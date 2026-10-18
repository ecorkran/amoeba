"""Layering and single-definition rules for the change feed and detection.

Rule 1: the store imports nothing from upstream, the process, or the feed.
Rule 2: the feed follower imports nothing from the process.
Rule 3: no module this slice adds spells a change kind or detection outcome as
a string literal; each names the enum member instead.
Rule 4: inspection imports nothing from the CLI, the server, or the process.
Rule 5: no server module but ``serve/errors.py`` spells an API error code as a
string literal or an error status (400-599) as an integer literal.
"""

from __future__ import annotations

import ast
from pathlib import Path

from amoeba.serve.errors import ApiErrorCode
from amoeba.store.feed_models import ChangeKind, DetectionOutcome

SRC = Path(__file__).parents[1] / "src" / "amoeba"

FORBIDDEN_FOR_STORE = ("amoeba.upstream", "amoeba.process", "amoeba.feed")
FORBIDDEN_FOR_FEED = ("amoeba.process",)
FORBIDDEN_FOR_INSPECTION = ("amoeba.cli", "amoeba.serve", "amoeba.process")

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
    "inspection/feed.py",
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


def test_rule_4_inspection_imports_no_cli_serve_or_process() -> None:
    """The listings are shared by the CLI and the server, so own neither."""
    assert _violations("inspection", FORBIDDEN_FOR_INSPECTION) == []


def test_rule_3_no_vocabulary_literal_in_this_slices_modules() -> None:
    for relative in SINGLE_DEFINITION_MODULES:
        path = SRC / relative
        assert path.is_file(), f"{relative} is listed but does not exist"
        literals = _string_literals(path) & _VOCABULARY
        assert not literals, f"{relative} spells {sorted(literals)} as literals"


#: The one module allowed to spell API error codes and statuses.
_ERROR_VOCABULARY_HOME = "errors.py"
_API_CODES = frozenset(member.value for member in ApiErrorCode)
_ERROR_STATUSES = range(400, 600)


def _int_literals(path: Path) -> set[int]:
    return {
        node.value
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        if isinstance(node, ast.Constant)
        and isinstance(node.value, int)
        and not isinstance(node.value, bool)
    }


def _error_vocabulary_violations(directory: Path) -> list[str]:
    """Each module in ``directory``, other than errors.py, spelling a code or status."""
    found: list[str] = []
    for path in sorted(directory.rglob("*.py")):
        if path.name == _ERROR_VOCABULARY_HOME:
            continue
        codes = sorted(_string_literals(path) & _API_CODES)
        statuses = sorted(v for v in _int_literals(path) if v in _ERROR_STATUSES)
        if codes or statuses:
            found.append(f"{path.name} spells {codes} {statuses}")
    return found


def test_rule_5_only_errors_py_spells_an_api_code_or_status() -> None:
    assert _error_vocabulary_violations(SRC / "serve") == []


def test_rule_5_reports_a_code_and_a_status(tmp_path: Path) -> None:
    (tmp_path / "handler.py").write_text(
        'def handle() -> tuple[str, int]:\n    return "not_found", 404\n',
        encoding="utf-8",
    )

    assert _error_vocabulary_violations(tmp_path) == [
        "handler.py spells ['not_found'] [404]"
    ]
