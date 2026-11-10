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
``answering.settings`` and its type module. ``operations`` does not import ``cli``.
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
}
#: package -> the only ``amoeba`` modules outside itself it may import.
ONLY_ALLOWED: dict[str, tuple[str, ...]] = {
    "config": ("amoeba.answering.settings", "amoeba.answering.values"),
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
