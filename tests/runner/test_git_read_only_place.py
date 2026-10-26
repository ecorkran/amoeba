"""``git`` is started in one place only: ``runner/git_read.py`` (slice 128, D10).

The allowlist in ``git_read`` stops a forbidden subcommand only for calls made through
it. This test is what makes it the only path: no other Runner module may build an
argument vector that starts with the executable ``git``.
"""

from __future__ import annotations

import ast
from pathlib import Path

from amoeba.runner import git_read

RUNNER = Path(git_read.__file__).parent
DEFINING_FILE = Path(git_read.__file__)
EXECUTABLE = git_read.GIT_EXECUTABLE


def _starts_a_git_command(path: Path) -> list[int]:
    """Lines where a list or tuple literal has ``"git"`` as its first element."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.List | ast.Tuple)
        and node.elts
        and isinstance(node.elts[0], ast.Constant)
        and node.elts[0].value == EXECUTABLE
    ]


def test_no_other_runner_module_builds_a_git_command() -> None:
    others = [p for p in sorted(RUNNER.rglob("*.py")) if p != DEFINING_FILE]
    assert others
    for path in others:
        lines = _starts_a_git_command(path)
        assert not lines, f"{path.name} builds a git command at line(s) {lines}"
