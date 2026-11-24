"""Layering of the packages under ``src/amoeba`` (slice 222, Component Structure).

```
cli ──► operations ──► store ──► answering.values
             │   └────► config ──► answering.settings
             └────────► upstream, answering
```

``store`` imports nothing from ``config``, ``operations`` or ``cli``. ``answering``
imports nothing from ``store``, ``config``, ``operations`` or ``cli`` (``store`` and
``config`` import its value and settings modules, never the reverse). ``upstream``
imports nothing from ``answering`` or the packages above it. ``config`` imports only
``answering.settings``, its type module and ``store.vocabulary`` (the closed
vocabularies, a leaf module: ``default_consumed`` is a ``ConsumedMode``).
``operations`` does not import ``cli``.
An import of a package that no longer exists is not checked here: it fails pyright.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

SRC = Path(__file__).parents[1] / "src" / "amoeba"
ROOT = "amoeba"

#: package -> the ``amoeba`` packages (or modules) it may not import.
FORBIDDEN: dict[str, tuple[str, ...]] = {
    "answering": (
        "amoeba.store",
        "amoeba.config",
        "amoeba.operations",
        "amoeba.cli",
    ),
    "store": ("amoeba.config", "amoeba.operations", "amoeba.cli"),
    "upstream": (
        "amoeba.answering",
        "amoeba.config",
        "amoeba.store",
        "amoeba.operations",
        "amoeba.cli",
    ),
    "operations": ("amoeba.cli",),
    # The client talks to the hub over the wire; it never touches a store (260).
    "client": ("amoeba.store", "amoeba.hub", "amoeba.upstream"),
    # The hub takes its store opener and operations from the commands that run it.
    "hub": (
        "amoeba.client",
        "amoeba.upstream",
        "amoeba.cli",
        "amoeba.mcp",
        "amoeba.wiring",
        "amoeba.wiring_door",
        "amoeba.wiring_gather",
        "amoeba.wiring_messages",
        "amoeba.wiring_presence",
        "amoeba.wiring_registry",
        "amoeba.wiring_release",
        "amoeba.wiring_releases",
        "amoeba.wiring_results",
    ),
}
#: package -> the only ``amoeba`` modules outside itself it may import.
ONLY_ALLOWED: dict[str, tuple[str, ...]] = {
    "config": (
        "amoeba.answering.settings",
        "amoeba.answering.values",
        "amoeba.store.vocabulary",
    ),
    # The client and the hub's shared package depends on nothing of ours (slice 260).
    "wire": (),
}


def _imported_names(source: str) -> set[str]:
    """Every module path and every ``module.name`` an import statement mentions."""
    names: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
            names.update(f"{node.module}.{alias.name}" for alias in node.names)
    return names


def _mentions(names: set[str], prefix: str) -> bool:
    return any(name == prefix or name.startswith(prefix + ".") for name in names)


def forbidden_imports(source: str, forbidden: tuple[str, ...]) -> list[str]:
    """The ``forbidden`` packages ``source`` imports from."""
    names = _imported_names(source)
    return [prefix for prefix in forbidden if _mentions(names, prefix)]


def disallowed_imports(
    source: str, package: str, allowed: tuple[str, ...]
) -> list[str]:
    """The ``amoeba`` imports of ``source`` outside ``package`` and not allowed."""
    own = f"{ROOT}.{package}"
    return sorted(
        name
        for name in _imported_names(source)
        if (name == ROOT or name.startswith(ROOT + "."))
        and not _mentions({name}, own)
        # ``from amoeba import x`` names a module of the root package: x is checked
        # through the ``amoeba.x`` entry, so the bare root is skipped.
        and name != ROOT
        and not any(
            _mentions({name}, ok) or ok.startswith(name + ".") for ok in allowed
        )
    )


def _modules(package: str) -> list[Path]:
    files = sorted((SRC / package).rglob("*.py"))
    assert files, f"amoeba.{package} has no source"
    return files


@pytest.mark.parametrize("package", sorted(FORBIDDEN))
def test_package_does_not_import_what_it_may_not(package: str) -> None:
    for path in _modules(package):
        found = forbidden_imports(path.read_text(encoding="utf-8"), FORBIDDEN[package])
        assert not found, f"{path.relative_to(SRC)} imports {found}"


@pytest.mark.parametrize("package", sorted(ONLY_ALLOWED))
def test_package_imports_only_what_it_is_allowed(package: str) -> None:
    for path in _modules(package):
        found = disallowed_imports(
            path.read_text(encoding="utf-8"), package, ONLY_ALLOWED[package]
        )
        assert not found, f"{path.relative_to(SRC)} imports {found}"


def _module_file(name: str) -> Path | None:
    base = SRC.parent.joinpath(*name.split("."))
    for candidate in (base.with_suffix(".py"), base / "__init__.py"):
        if candidate.exists():
            return candidate
    return None


def _reached_from(package: str) -> dict[str, str]:
    """Every ``amoeba`` module ``package`` reaches by following imports, each with
    the module that imported it first."""
    reached: dict[str, str] = {}
    pending = [
        (f"{ROOT}.{package}", f"amoeba.{package}"),
        *(
            (".".join(path.relative_to(SRC.parent).with_suffix("").parts), "")
            for path in _modules(package)
        ),
    ]
    while pending:
        name, importer = pending.pop()
        path = _module_file(name)
        if name in reached or path is None:
            continue
        reached[name] = importer
        for imported in _imported_names(path.read_text(encoding="utf-8")):
            if imported.startswith(ROOT + "."):
                pending.append((imported, name))
    return reached


def test_the_hub_reaches_no_client_module_through_any_import() -> None:
    # Direct imports are checked above; this follows them through ``operations``,
    # ``store`` and the rest, so a hub never depends on the client indirectly.
    reached = _reached_from("hub")
    leaked = sorted(name for name in reached if name.startswith("amoeba.client"))

    assert not leaked, {name: reached[name] for name in leaked}


#: Modules the hub part uses to look up callers and members (slice 261, D5, D6): they
#: import nothing from ``upstream``, so they never run ``cf``, ``git`` or ``sq``. A rule
#: about one module is its own test: the tables above are per package.
HUB_SIDE_MODULES = (
    "operations/caller.py",
    "operations/here_document.py",
    "operations/runs_document.py",
)


@pytest.mark.parametrize("module", HUB_SIDE_MODULES)
def test_a_hub_side_lookup_module_imports_nothing_from_upstream(module: str) -> None:
    source = (SRC / module).read_text(encoding="utf-8")

    assert forbidden_imports(source, ("amoeba.upstream",)) == []


def test_the_forbidden_rule_catches_each_way_of_importing() -> None:
    forbidden = ("amoeba.answering",)

    assert forbidden_imports("import amoeba.answering.values\n", forbidden)
    assert forbidden_imports("from amoeba.answering import values\n", forbidden)
    assert forbidden_imports(
        "from amoeba.answering.values import DeclineReason\n", forbidden
    )


def test_the_forbidden_rule_ignores_unrelated_imports() -> None:
    forbidden = ("amoeba.answering",)

    assert not forbidden_imports(
        "from amoeba.upstream.squadron import launch\n", forbidden
    )
    assert not forbidden_imports(
        "from amoeba import answering_notes\nimport json\n", forbidden
    )


def test_the_allow_list_rule_catches_a_stray_amoeba_import() -> None:
    allowed = ("amoeba.answering.settings",)

    assert disallowed_imports(
        "from amoeba.store.store import Store\n", "config", allowed
    )
    assert disallowed_imports("import amoeba.operations\n", "config", allowed)
    assert not disallowed_imports(
        "from amoeba.answering.settings import ModelAlias\nimport yaml\n",
        "config",
        allowed,
    )
    assert not disallowed_imports(
        "from amoeba.config.home import x\n", "config", allowed
    )


#: The client part (slice 261, D5): the modules that run ``cf``, ``git`` or ``sq``.
#: The hub never runs those, so it never reaches them through any import.
CLIENT_PART_MODULES = (
    "amoeba.operations.here",
    "amoeba.operations.naming",
    "amoeba.operations.run_gather",
    "amoeba.operations.add_gather",
)
#: The functions that run ``cf``; only the client part's modules import them.
CF_CALL_FUNCTIONS = frozenset({"project_of", "project_details"})
CF_CALLERS = frozenset(
    {"operations/here.py", "operations/naming.py", "operations/run_gather.py"}
)


def _reached_from_module(name: str) -> dict[str, str]:
    """Every ``amoeba`` module ``name`` reaches by following imports (parents
    included, as importing a module imports its package), with its first importer."""
    reached: dict[str, str] = {}
    pending = [(name, "")]
    while pending:
        current, importer = pending.pop()
        path = _module_file(current)
        if current in reached or path is None:
            continue
        reached[current] = importer
        parts = current.split(".")
        pending.extend((".".join(parts[:i]), current) for i in range(2, len(parts)))
        for imported in _imported_names(path.read_text(encoding="utf-8")):
            if imported.startswith(ROOT + "."):
                pending.append((imported, current))
    return reached


def test_only_the_client_part_imports_the_functions_that_run_cf() -> None:
    """Direct imports of ``project_of`` and ``project_details``
    (``operations.add_gather`` reaches them through ``here``). A type-only import
    (``CFProject``, ``CFProjectNotFound``) is allowed: ``working_directory`` keeps its
    ``CFProject`` shape."""
    importers: set[str] = set()
    for path in sorted(SRC.rglob("*.py")):
        if "upstream" in path.relative_to(SRC).parts:
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom) and any(
                alias.name in CF_CALL_FUNCTIONS for alias in node.names
            ):
                importers.add(str(path.relative_to(SRC)))

    assert importers == CF_CALLERS


def test_the_hub_reaches_no_client_part_module_through_any_import() -> None:
    reached = _reached_from("hub")
    leaked = sorted(name for name in CLIENT_PART_MODULES if name in reached)

    assert not leaked, {name: reached[name] for name in leaked}


def test_served_reaches_no_client_part_module_through_any_import() -> None:
    reached = _reached_from_module("amoeba.operations.served")
    leaked = sorted(name for name in CLIENT_PART_MODULES if name in reached)

    assert not leaked, {name: reached[name] for name in leaked}


def test_the_walk_finds_an_import_it_should() -> None:
    """The walk itself: ``wiring_gather`` imports the client part, so it reaches it."""
    reached = _reached_from_module("amoeba.wiring_gather")

    assert "amoeba.operations.here" in reached
    assert "amoeba.operations.run_gather" in reached


# --- slice 262: steps and the client-run modules --------------------------------

#: A module that is not a package: the modules a client-run command is made of reach
#: the store only through ``Steps`` (262 D3), so none imports ``amoeba.store.store``.
#: The table grows module by module as each one moves onto steps. ``FORBIDDEN`` above
#: is keyed by package; this one is keyed by file and checked by the same walk.
MODULE_FORBIDDEN: dict[str, tuple[str, ...]] = {
    "operations/resume.py": ("amoeba.store.store",),
    "operations/resume_attempt.py": ("amoeba.store.store",),
}
#: What runs ``cf``, ``sq`` or ``git``: the whole ``upstream`` package and the module
#: that starts children. A step runs on the hub, which has none of the three tools.
RUNS_EXTERNAL_TOOLS = (
    "amoeba.upstream",
    "amoeba.operations.processes",
    "amoeba.operations.deps",
)
#: The one ``upstream`` module that runs nothing: it only cuts text to a bound.
UPSTREAM_ALLOWED_TO_STEPS = ("amoeba.upstream.bounded_text",)
#: The only ``answering`` modules a step may reach: they read no file. The rest of
#: ``answering`` reads the checkout's sources, which only the client may do.
ANSWERING_ALLOWED_TO_STEPS = frozenset(
    {
        "amoeba.answering.values",
        "amoeba.answering.settings",
        "amoeba.answering.gate",
    }
)


@pytest.mark.parametrize("module", sorted(MODULE_FORBIDDEN))
def test_a_client_run_module_does_not_import_what_its_row_forbids(module: str) -> None:
    source = (SRC / module).read_text(encoding="utf-8")

    assert forbidden_imports(source, MODULE_FORBIDDEN[module]) == []


def _step_sources() -> list[Path]:
    return sorted((SRC / "operations" / "steps").glob("*.py"))


def _answering_modules_that_read_files() -> tuple[str, ...]:
    """Every ``answering`` module a step may not import: all but the allowed ones."""
    names = (
        f"{ROOT}.answering.{path.stem}"
        for path in sorted((SRC / "answering").glob("*.py"))
        if path.stem != "__init__"
    )
    return tuple(name for name in names if name not in ANSWERING_ALLOWED_TO_STEPS)


def test_steps_import_no_module_that_runs_cf_sq_or_git() -> None:
    assert _step_sources()
    for path in _step_sources():
        source = path.read_text(encoding="utf-8")
        names = _imported_names(source) - {
            name
            for name in _imported_names(source)
            if any(_mentions({name}, ok) for ok in UPSTREAM_ALLOWED_TO_STEPS)
        }
        found = [
            prefix
            for prefix in RUNS_EXTERNAL_TOOLS
            if any(_mentions({name}, prefix) for name in names)
        ]
        assert not found, f"{path.relative_to(SRC)} imports {found}"


def test_steps_import_nothing_from_answering_that_reads_a_file() -> None:
    forbidden = _answering_modules_that_read_files()
    assert forbidden
    for path in _step_sources():
        found = forbidden_imports(path.read_text(encoding="utf-8"), forbidden)
        assert not found, f"{path.relative_to(SRC)} imports {found}"
