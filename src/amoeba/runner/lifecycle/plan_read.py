"""The ``cf`` commands the Runner runs, spelled once (D11).

The shape probes in ``probes.py`` and the plan read both import these, so a command
cannot be probed in one form and read in another. Executable, flags and subcommands
are defined here and nowhere else; ``-p <id>`` is appended by the caller.
"""

from __future__ import annotations

from typing import Final

CF_EXECUTABLE: Final = "cf"
CF_PROJECT_FLAG: Final = "-p"
CF_JSON_FLAG: Final = "--json"
#: Include every initiative, not only the active one.
CF_ALL_FLAG: Final = "-a"

#: Commands without the executable or the ``-p <id>`` suffix.
CF_STATUS_COMMAND: Final = ("status", CF_JSON_FLAG)
CF_INITIATIVES_COMMAND: Final = ("list", "initiatives", CF_JSON_FLAG, CF_ALL_FLAG)


def slice_list_command(initiative_index: int) -> tuple[str, ...]:
    """The slice-list command for one initiative."""
    return ("list", "slices", str(initiative_index), CF_JSON_FLAG)
