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
        plan_read.CF_SET_COMMAND,
    }
)


def test_no_other_runner_module_spells_a_cf_command_word() -> None:
    others = [p for p in sorted(RUNNER.rglob("*.py")) if p != DEFINING_FILE]
    assert others
    for path in others:
        clashes = COMMAND_WORDS.intersection(string_constants(path))
        assert not clashes, f"{path.name} spells {sorted(clashes)}"
