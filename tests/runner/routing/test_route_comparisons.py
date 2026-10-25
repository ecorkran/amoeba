"""No route is chosen in a code branch outside the engine.

``Route`` members are named only in ``routing/engine.py`` (evaluation, eligibility
and the effect mapping) and ``routing/validate.py`` (which checks the grammar each
route accepts and never chooses one). Naming a member anywhere else under
``runner/`` is how a route would get chosen in code.
"""

from __future__ import annotations

import ast
from pathlib import Path

from amoeba.runner.routing import engine, validate
from amoeba.store import Route

RUNNER = Path(engine.__file__).parents[1]
ALLOWED = {Path(engine.__file__), Path(validate.__file__)}
MEMBERS = {member.name for member in Route}


def _member_uses(path: Path) -> list[int]:
    """Line numbers of ``Route.<MEMBER>`` in ``path``."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == Route.__name__
        and node.attr in MEMBERS
    ]


def test_route_members_are_named_only_in_the_engine_and_validation() -> None:
    modules = sorted(RUNNER.rglob("*.py"))
    assert ALLOWED <= set(modules)
    for path in modules:
        if path in ALLOWED:
            continue
        assert not _member_uses(path), f"{path} names a Route member"


def test_the_allowed_modules_do_name_members() -> None:
    # Guards the guard: if the scan stopped finding members, the test above
    # would pass for the wrong reason.
    for path in ALLOWED:
        assert _member_uses(path), f"{path.name} no longer names a Route member"
