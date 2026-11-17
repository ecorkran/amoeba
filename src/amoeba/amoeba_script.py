"""The installed ``amoeba`` script, for starting detached ``amoeba`` children
(slices 226, 242).

At the package root so both the MCP server (226) and ``operations`` (242's start of
``handle-pause`` for held questions, through ``Deps.amoeba_script``) can use it;
``operations`` may not import ``mcp``.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Final

from amoeba.operations.names import OperationName

AMOEBA_SCRIPT_NAME: Final = "amoeba"
#: Keeps the child's stdout log machine-readable (229 D1): the CLI's text is for people.
JSON_FLAG: Final = "--json"
#: Marks the end of options, so a run id that starts with ``-`` is not read as a flag.
END_OF_OPTIONS: Final = "--"


class AmoebaScriptMissing(Exception):
    """The ``amoeba`` script is not beside the running interpreter."""


def resolve_amoeba_script() -> Path:
    """The ``amoeba`` script installed beside this interpreter.

    ``uv tool install`` puts ``amoeba`` and ``amoeba-mcp`` in one environment, so the
    script is next to ``sys.executable`` (not resolved: a symlinked interpreter would
    lead to another directory).

    Raises:
        AmoebaScriptMissing: There is no such file; the message names the path.
    """
    script = Path(sys.executable).parent / AMOEBA_SCRIPT_NAME
    if not script.exists():
        raise AmoebaScriptMissing(
            f"the amoeba script is not at {script}; install with "
            "`uv tool install --force <repo>` so amoeba and amoeba-mcp share one "
            "environment"
        )
    return script


def handle_pause_argv(script: Path, run_id: str) -> list[str]:
    """The argv of a detached ``amoeba handle-pause --json -- <run_id>``."""
    return [
        str(script),
        OperationName.HANDLE_PAUSE.cli_name,
        JSON_FLAG,
        END_OF_OPTIONS,
        run_id,
    ]
