"""Every ``cf`` command word is spelled once, in ``context_forge/target_read.py``."""

from __future__ import annotations

from pathlib import Path
from typing import Final

from ast_strings import string_constants

from amoeba.upstream.context_forge import target_read as plan_read

#: Where ``cf`` is spoken: its own package and the answering library. ``sq`` modules
#: spell ``--json`` for themselves, so the whole tree is not scanned.
SOURCE_ROOT = Path(plan_read.__file__).parents[2]
SCANNED = (SOURCE_ROOT / "upstream" / "context_forge", SOURCE_ROOT / "answering")
DEFINING_FILE = Path(plan_read.__file__)

#: The command words a second spelling of which would be a second definition.
#: ``-p`` is not listed: ``sq`` has its own ``-p`` (``launch.SQ_PARAM_FLAG``).
COMMAND_WORDS: Final = frozenset(
    {
        plan_read.CF_EXECUTABLE,
        plan_read.CF_JSON_FLAG,
        "config",
        plan_read.CF_KEY_INTEGRATION_BRANCH,
        plan_read.CF_ALL_FLAG,
        plan_read.CF_LIST_COMMAND,
        plan_read.CF_INITIATIVES_WORD,
        plan_read.CF_SLICES_WORD,
    }
)


def test_no_other_module_spells_a_cf_command_word() -> None:
    others = [
        p
        for directory in SCANNED
        for p in sorted(directory.rglob("*.py"))
        if p != DEFINING_FILE
    ]
    assert others
    for path in others:
        clashes = COMMAND_WORDS.intersection(string_constants(path))
        assert not clashes, f"{path.name} spells {sorted(clashes)}"


def test_no_code_path_writes_to_cf() -> None:
    """Amoeba reads CF and never writes it (slice 132, D3): no ``cf set``."""
    assert not hasattr(plan_read, "CF_SET_COMMAND")
    for path in sorted(SOURCE_ROOT.rglob("*.py")):
        assert "set_slice_argv" not in path.read_text(encoding="utf-8"), path.name
