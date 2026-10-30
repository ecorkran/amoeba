"""Every ``cf`` command word is spelled once, in ``runner/lifecycle/plan_read.py``."""

from __future__ import annotations

from pathlib import Path
from typing import Final

from ast_strings import string_constants

from amoeba.runner.lifecycle import plan_read

RUNNER = Path(plan_read.__file__).parents[1]
DEFINING_FILE = Path(plan_read.__file__)

#: The command words a second spelling of which would be a second definition.
#: ``-p`` is not listed: ``sq`` has its own ``-p`` (``launch.SQ_PARAM_FLAG``).
COMMAND_WORDS: Final = frozenset(
    {
        plan_read.CF_EXECUTABLE,
        plan_read.CF_JSON_FLAG,
        plan_read.CF_ALL_FLAG,
        "initiatives",
        "slices",
        "config",
        plan_read.CF_WORKTREE_FLAG,
        plan_read.CF_KEY_INTEGRATION_BRANCH,
        plan_read.CF_KEY_REVIEW_GATE_EFFECTIVE_DATE,
    }
)


def test_no_other_runner_module_spells_a_cf_command_word() -> None:
    others = [p for p in sorted(RUNNER.rglob("*.py")) if p != DEFINING_FILE]
    assert others
    for path in others:
        clashes = COMMAND_WORDS.intersection(string_constants(path))
        assert not clashes, f"{path.name} spells {sorted(clashes)}"


def test_no_code_path_writes_to_cf() -> None:
    """The Runner reads CF and never writes it (slice 132, D3): no ``cf set``."""
    assert not hasattr(plan_read, "CF_SET_COMMAND")
    for path in sorted(RUNNER.rglob("*.py")):
        assert "set_slice_argv" not in path.read_text(encoding="utf-8"), path.name
