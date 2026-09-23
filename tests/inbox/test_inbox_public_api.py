"""Pin ``amoeba.inbox``'s public surface and the one-way dependency direction.

Named ``test_inbox_public_api.py``, not ``test_public_api.py``: that basename
already belongs to the store's surface test, and duplicate basenames break
collection.

What the LLD's Component Structure requires, made mechanical:

- ``submit`` is the inbox's only write path; everything else exported reads.
- ``amoeba.inbox`` never imports ``Store`` — it cannot open a store at all.
- ``amoeba.store`` never imports ``amoeba.inbox``.

The import checks walk the AST, per the testing rules, so a wrapped import
cannot slip past them.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import amoeba.inbox as inbox_package

SOURCE_DIR = Path(__file__).parent.parent.parent / "src" / "amoeba"

#: The exported contract, written out rather than derived from ``__all__``.
EXPECTED_EXPORTS = {
    # The one write path
    "submit",
    # Read-only listings
    "failed",
    "pending",
    "quarantined",
    # Transfer objects
    "FailedSubmission",
    "PendingSubmission",
    "QuarantinedSubmission",
    # Exceptions
    "EnvelopeError",
    "InboxSubmitError",
    "InvalidSubmissionError",
    "SubmissionWriteError",
}

#: The only exported function that writes anything.
WRITE_PATHS = {"submit"}


def _imported_modules(source: str) -> set[str]:
    """Every module ``source`` imports, absolute, as dotted names."""
    found: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            found.add(node.module)
            found.update(f"{node.module}.{alias.name}" for alias in node.names)
    return found


def _sources_under(package: str) -> list[tuple[str, str]]:
    """``(name, source)`` for every module in a package."""
    return [
        (path.name, path.read_text(encoding="utf-8"))
        for path in sorted((SOURCE_DIR / package).rglob("*.py"))
    ]


def test_the_export_surface_is_exactly_the_contract() -> None:
    assert set(inbox_package.__all__) == EXPECTED_EXPORTS


def test_submit_is_the_only_exported_write_path() -> None:
    """Every other exported function is a listing, and listings only read."""
    functions = {
        name
        for name in inbox_package.__all__
        if inspect.isfunction(getattr(inbox_package, name))
    }

    assert functions - WRITE_PATHS == {"failed", "pending", "quarantined"}
    assert functions & WRITE_PATHS == WRITE_PATHS


def test_the_inbox_never_imports_store() -> None:
    """It imports store vocabularies and path rules — never the class."""
    for name, source in _sources_under("inbox"):
        imports = _imported_modules(source)
        assert "amoeba.store.Store" not in imports, name
        assert "amoeba.store.store" not in imports, name


def test_the_store_never_imports_the_inbox() -> None:
    """The dependency runs one way: ``apply_submission`` takes plain values."""
    for name, source in _sources_under("store"):
        offenders = {
            module
            for module in _imported_modules(source)
            if module.startswith("amoeba.inbox")
        }
        assert offenders == set(), f"{name} imports {sorted(offenders)}"


def test_the_import_scan_sees_a_wrapped_violation() -> None:
    """The scan itself is verified, so a passing check means something."""
    wrapped = "from amoeba.store import (\n    Store,\n)\nimport amoeba.inbox\n"

    imports = _imported_modules(wrapped)

    assert "amoeba.store.Store" in imports
    assert "amoeba.inbox" in imports
