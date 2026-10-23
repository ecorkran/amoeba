"""Layering and single-definition rules for the change feed and detection.

Rule 1: the store imports nothing from upstream, the process, or the feed.
Rule 2: the feed follower imports nothing from the process.
Rule 3: no module this slice adds spells a change kind or detection outcome as
a string literal; each names the enum member instead.
Rule 4: inspection imports nothing from the CLI, the server, or the process.
Rule 5: no server module but ``serve/errors.py`` spells an API error code as a
string literal or an error status (400-599) as an integer literal.
Rule 6: the server imports nothing from the CLI or the process.
Rule 7: only ``cli/serve.py`` imports the server, so no other command loads uvicorn.
Rule 8: the server takes from ``amoeba.inbox`` only ``submit`` and its two
errors, takes ``SubmissionKind`` from its defining module, and never calls
``Store.open``.
Rule 9: ``process/run_pruning.py`` is pure: it imports only the standard library
and the outcome-document model it shares with the ``sq_run`` observer.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

from amoeba.serve.errors import ApiErrorCode
from amoeba.store.feed_models import ChangeKind, DetectionOutcome

SRC = Path(__file__).parents[1] / "src" / "amoeba"

FORBIDDEN_FOR_STORE = ("amoeba.upstream", "amoeba.process", "amoeba.feed")
FORBIDDEN_FOR_FEED = ("amoeba.process",)
FORBIDDEN_FOR_INSPECTION = ("amoeba.cli", "amoeba.serve", "amoeba.process")
FORBIDDEN_FOR_SERVE = ("amoeba.cli", "amoeba.process")

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


def test_rule_6_the_server_imports_no_cli_or_process() -> None:
    """It is not the resident process and cannot reach its host or tenants."""
    assert _violations("serve", FORBIDDEN_FOR_SERVE) == []


#: The one module allowed to import the server.
_SERVE_IMPORTER = SRC / "cli" / "serve.py"


def test_rule_7_only_cli_serve_imports_the_server() -> None:
    importers = [
        str(path.relative_to(SRC))
        for path in sorted(SRC.rglob("*.py"))
        if path != _SERVE_IMPORTER
        and (SRC / "serve") not in path.parents
        and _mentions(_imported_names(path), "amoeba.serve")
    ]
    assert importers == []


#: Everything the server may take from the inbox: its one write path and errors.
_INBOX_ALLOWED = frozenset({"submit", "InvalidSubmissionError", "SubmissionWriteError"})
_INBOX = "amoeba.inbox"
_SUBMISSION_KIND_HOME = "amoeba.store.inbox_models"


def _inbox_violations(path: Path) -> list[str]:
    found: list[str] = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            found.extend(
                f"{path.name}: import {alias.name}"
                for alias in node.names
                if _mentions({alias.name}, _INBOX)
            )
        elif isinstance(node, ast.ImportFrom) and node.module:
            names = {alias.name for alias in node.names}
            if _mentions({node.module}, _INBOX):
                found.extend(
                    f"{path.name}: {node.module}.{name}"
                    for name in sorted(names - _INBOX_ALLOWED)
                )
            if "SubmissionKind" in names and node.module != _SUBMISSION_KIND_HOME:
                found.append(f"{path.name}: SubmissionKind from {node.module}")
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "open"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "Store"
        ):
            found.append(f"{path.name}: Store.open")
    return found


def test_rule_8_the_server_writes_only_through_submit() -> None:
    found = [
        v
        for path in sorted((SRC / "serve").rglob("*.py"))
        for v in _inbox_violations(path)
    ]
    assert found == []


def test_rule_8_reports_every_kind_of_violation(tmp_path: Path) -> None:
    module = tmp_path / "bad.py"
    module.write_text(
        "from amoeba.inbox import pending, submit\n"
        "from amoeba.inbox import SubmissionKind\n"
        "import amoeba.inbox.durable\n"
        "Store.open(path)\n",
        encoding="utf-8",
    )

    assert _inbox_violations(module) == [
        "bad.py: amoeba.inbox.pending",
        "bad.py: amoeba.inbox.SubmissionKind",
        "bad.py: SubmissionKind from amoeba.inbox",
        "bad.py: import amoeba.inbox.durable",
        "bad.py: Store.open",
    ]


#: Rule 9: the only non-standard-library module the selection rule may import.
_PRUNING_ALLOWED = "amoeba.process.sq_outcome"
_RUN_PRUNING = SRC / "process" / "run_pruning.py"


def _pruning_violations(path: Path) -> list[str]:
    return sorted(
        name
        for name in _top_level_imports(path)
        if name != _PRUNING_ALLOWED
        and name.split(".")[0] not in sys.stdlib_module_names
    )


def _top_level_imports(path: Path) -> set[str]:
    """Each imported module, as written: ``import a.b`` and ``from a.b import c``."""
    modules: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_rule_9_run_pruning_imports_only_the_standard_library_and_the_outcome() -> None:
    assert _pruning_violations(_RUN_PRUNING) == []


def test_rule_9_reports_the_store_and_any_other_module(tmp_path: Path) -> None:
    module = tmp_path / "bad.py"
    module.write_text(
        "from __future__ import annotations\n"
        "from datetime import datetime\n"
        "from amoeba.process.sq_outcome import RunOutcomeDocument\n"
        "from amoeba.store import Store\n"
        "import pydantic\n",
        encoding="utf-8",
    )

    assert _pruning_violations(module) == ["amoeba.store", "pydantic"]


#: Slice 120, D8: pruning asks Squadron through ``sq runs wait`` and never reads a
#: run-state file, so these modules may not reach the run-file parser or the
#: runs-directory default.
_PRUNING_MODULES = (SRC / "cli" / "prune.py", SRC / "process" / "run_pruning.py")
_RUN_FILE_READERS = ("amoeba.process.observers.sq_runs", "DEFAULT_SQ_RUNS_DIR")


def _run_file_reads(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
    return sorted(found & set(_RUN_FILE_READERS))


def test_pruning_does_not_import_the_run_file_parser_or_the_runs_directory() -> None:
    for module in _PRUNING_MODULES:
        assert _run_file_reads(module) == [], module.name


def test_the_run_file_read_check_reports_both_imports(tmp_path: Path) -> None:
    module = tmp_path / "bad.py"
    module.write_text(
        "from amoeba.process.observers.sq_runs import parse_run_file\n"
        "from amoeba.process.settings import DEFAULT_SQ_RUNS_DIR\n",
        encoding="utf-8",
    )

    assert _run_file_reads(module) == [
        "DEFAULT_SQ_RUNS_DIR",
        "amoeba.process.observers.sq_runs",
    ]
