"""Mechanical guard: only the resident process opens a store read-write.

The sole-writer model is enforced in two parts. The instance lock guarantees at
most one resident process per supervisor directory; this test guarantees that
*within Amoeba* nothing but ``process/project_stores.py`` (and the one exempted
operator script below) reaches for the read-write ``Store.open``. Together they
make the model structural rather than a sentence in a contract document.

**Scanned roots**: ``src/amoeba/`` and ``scripts/``. The latter was added
after a review found ``scripts/demo_journal.py`` doing a real read-write open
outside the scanned tree — an intentional operator-facing demo, but invisible
to this guard by construction. Rather than widen ``src/amoeba/`` itself (which
would misrepresent where the exemption actually lives), ``scripts/`` is
scanned as its own root and the demo script is named explicitly in
:data:`PERMITTED_SCRIPTS`, so the exemption is visible here rather than
silently unenforced.

**What this guard does not cover**, stated plainly rather than implied away:

- A third party that imports ``amoeba.store`` and calls ``Store.open`` itself.
  Nothing in a library can prevent that, and this guard does not pretend to. It
  makes the mistake impossible to make *by accident inside Amoeba*, which is
  the realistic failure.
- ``Store.open_temporary``, which creates an in-memory database that no other
  process can see, so it cannot violate single-writer.
- Tests, which legitimately open stores read-write to stage fixtures. The scan
  covers ``src/amoeba/`` and ``scripts/`` only.
- Raw ``sqlite3.connect`` calls that bypass ``Store`` entirely. The store
  package itself is where those live, by construction.

The scan walks the parsed AST rather than grepping, per the testing rules: a
call split across lines defeats a per-line search.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
SOURCE_DIR = REPO_ROOT / "src" / "amoeba"
SCRIPTS_DIR = REPO_ROOT / "scripts"

#: The read-write constructor. Calling it anywhere but a permitted module is
#: what this guard fails on.
READ_WRITE_OPEN = "open"

#: The class the call must be made on for it to count.
STORE_CLASS = "Store"

#: The **only** module under ``src/amoeba/`` permitted to open a store
#: read-write. Not a list that grows casually: adding to it widens the
#: sole-writer invariant, and the contract documents would have to say so.
PERMITTED_MODULES = frozenset({"process/project_stores.py"})

#: The **only** module under ``scripts/`` permitted to open a store
#: read-write. ``demo_journal.py`` is an operator-run demo, not part of the
#: resident process, and requires ``AMOEBA_STORE_DIR`` pointed at a scratch
#: directory before it can do anything — see its own module docstring.
PERMITTED_SCRIPTS = frozenset({"demo_journal.py"})

#: Constructors that are not the read-write open and are therefore ignored.
#: ``open_read_only`` is the whole point of the exercise; ``open_temporary``
#: makes a private in-memory database.
IGNORED_CONSTRUCTORS = frozenset({"open_read_only", "open_temporary"})


def _source_modules() -> list[Path]:
    """Every Python module under ``src/amoeba/``."""
    return sorted(SOURCE_DIR.rglob("*.py"))


def _script_modules() -> list[Path]:
    """Every Python module under ``scripts/``."""
    return sorted(SCRIPTS_DIR.rglob("*.py"))


def _relative(path: Path) -> str:
    """A module's path relative to the package root, for readable failures."""
    return path.relative_to(SOURCE_DIR).as_posix()


def _relative_to_scripts(path: Path) -> str:
    """A script's path relative to ``scripts/``, for readable failures."""
    return path.relative_to(SCRIPTS_DIR).as_posix()


def _read_write_open_calls(source: str) -> list[int]:
    """Line numbers of every ``Store.open(...)`` call in ``source``.

    Matches an attribute call whose attribute is ``open`` and whose value is
    the name ``Store`` — so ``Store.open_read_only`` and a local ``open()`` are
    both correctly left alone. Walking the AST means a call wrapped across
    lines is caught exactly as a single-line one is.
    """
    tree = ast.parse(source)
    found: list[int] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        function = node.func
        if not isinstance(function, ast.Attribute):
            continue
        if function.attr in IGNORED_CONSTRUCTORS:
            continue
        if function.attr != READ_WRITE_OPEN:
            continue
        if isinstance(function.value, ast.Name) and function.value.id == STORE_CLASS:
            found.append(node.lineno)

    return found


# --------------------------------------------------------------------------
# The scan is itself verified, so a passing guard means something
# --------------------------------------------------------------------------


def test_the_scan_finds_a_read_write_open() -> None:
    """A deliberate violation is detected — the self-check the task requires.

    This is the "introduce it by hand and confirm the guard fails" step, kept
    permanently as a test rather than performed once and forgotten.
    """
    violation = "from amoeba.store import Store\n\nstore = Store.open(path)\n"

    assert _read_write_open_calls(violation) == [3]


def test_the_scan_finds_a_wrapped_read_write_open() -> None:
    """Line wrapping does not hide a violation from an AST walk."""
    wrapped = (
        "from amoeba.store import Store\n\n"
        "store = Store.open(\n    path,\n    project_id='demo',\n)\n"
    )

    assert _read_write_open_calls(wrapped) == [3]


def test_the_scan_ignores_the_read_only_open() -> None:
    """``open_read_only`` is what every other module is supposed to use."""
    permitted = "from amoeba.store import Store\n\nStore.open_read_only(path)\n"

    assert _read_write_open_calls(permitted) == []


def test_the_scan_ignores_the_temporary_open() -> None:
    """An in-memory store is private to its process and cannot conflict."""
    permitted = "from amoeba.store import Store\n\nStore.open_temporary()\n"

    assert _read_write_open_calls(permitted) == []


def test_the_scan_ignores_unrelated_open_calls() -> None:
    """A builtin ``open`` or some other object's ``open`` is not a store write."""
    benign = (
        "from pathlib import Path\n\n"
        "handle = open('a-file.txt')\n"
        "other = something_else.open(path)\n"
    )

    assert _read_write_open_calls(benign) == []


# --------------------------------------------------------------------------
# The guard itself
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "module_path", _source_modules(), ids=lambda path: _relative(path)
)
def test_only_project_stores_opens_a_store_read_write(module_path: Path) -> None:
    """Only ``process/project_stores.py`` calls the read-write ``Store.open``."""
    relative = _relative(module_path)
    calls = _read_write_open_calls(module_path.read_text(encoding="utf-8"))

    if relative in PERMITTED_MODULES:
        return

    assert not calls, (
        f"{relative} calls the read-write Store.open at line(s) {calls}. "
        "Only process/project_stores.py may do that: it is the sole writer, "
        "guaranteed by the instance lock. Every other module must use "
        "Store.open_read_only."
    )


def test_the_permitted_module_exists_and_actually_opens_a_store() -> None:
    """The permitted module is real, and the permission is not vestigial.

    A guard whose allowlist names a module that no longer opens a store would
    pass while enforcing nothing, and the drift would be invisible.
    """
    for permitted in PERMITTED_MODULES:
        path = SOURCE_DIR / permitted
        assert path.exists(), f"{permitted} is permitted but does not exist"
        assert _read_write_open_calls(path.read_text(encoding="utf-8")), (
            f"{permitted} is permitted to open a store read-write but does "
            "not; either the allowlist or the module has drifted"
        )


def test_the_inspection_cli_is_covered_by_the_scan() -> None:
    """``cli/inspect.py`` is in the scanned set and is not exempt.

    Task 2.1's evidence supported true ``mode=ro``, so inspection holds a
    genuinely read-only handle and needs no exemption here. Had the fallback
    been taken, this is where the exemption would have had to be added — and
    both contract documents would have had to record the softened invariant.
    """
    inspect_module = SOURCE_DIR / "cli" / "inspect.py"

    assert inspect_module in set(_source_modules())
    assert "cli/inspect.py" not in PERMITTED_MODULES
    assert _read_write_open_calls(inspect_module.read_text(encoding="utf-8")) == []


def test_the_inbox_and_submit_cli_are_covered_by_the_scan() -> None:
    """``amoeba.inbox`` and ``cli/submit.py`` are scanned, and exempt from nothing.

    Both are how a part *outside* the process contributes state, so neither
    may hold a read-write store: ``submit`` writes a file, and the process
    applies it through the one permitted module.
    """
    scanned = set(_source_modules())
    inbox_modules = sorted((SOURCE_DIR / "inbox").glob("*.py"))
    submit_cli = SOURCE_DIR / "cli" / "submit.py"

    assert inbox_modules, "the inbox package must exist to be scanned"
    for module in [*inbox_modules, submit_cli]:
        assert module in scanned
        assert _relative(module) not in PERMITTED_MODULES
        assert _read_write_open_calls(module.read_text(encoding="utf-8")) == []


def test_the_permitted_set_is_exactly_project_stores() -> None:
    """Widening the sole-writer invariant is a deliberate, visible change.

    Still a set of **size one** after the extraction: the permission moved
    from ``process/host.py`` to ``process/project_stores.py``, it was not
    loosened to allow both.
    """
    assert PERMITTED_MODULES == frozenset({"process/project_stores.py"})


# --------------------------------------------------------------------------
# ``scripts/`` — added after a review found it outside the scanned set
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "script_path", _script_modules(), ids=lambda path: _relative_to_scripts(path)
)
def test_only_permitted_scripts_open_a_store_read_write(script_path: Path) -> None:
    """No script but the ones named in ``PERMITTED_SCRIPTS`` may write."""
    relative = _relative_to_scripts(script_path)
    calls = _read_write_open_calls(script_path.read_text(encoding="utf-8"))

    if relative in PERMITTED_SCRIPTS:
        return

    assert not calls, (
        f"scripts/{relative} calls the read-write Store.open at line(s) "
        f"{calls}. Only {sorted(PERMITTED_SCRIPTS)} are permitted to: add it "
        "to PERMITTED_SCRIPTS if this is a deliberate new operator tool, or "
        "use Store.open_read_only otherwise."
    )


def test_the_permitted_scripts_exist_and_actually_open_a_store() -> None:
    """Same drift check as the permitted module, for the scripts allowlist."""
    for permitted in PERMITTED_SCRIPTS:
        path = SCRIPTS_DIR / permitted
        assert path.exists(), f"{permitted} is permitted but does not exist"
        assert _read_write_open_calls(path.read_text(encoding="utf-8")), (
            f"{permitted} is permitted to open a store read-write but does "
            "not; either the allowlist or the script has drifted"
        )


def test_the_permitted_scripts_set_is_exactly_the_demo() -> None:
    """Widening this exemption is a deliberate, visible change too."""
    assert PERMITTED_SCRIPTS == frozenset({"demo_journal.py"})
