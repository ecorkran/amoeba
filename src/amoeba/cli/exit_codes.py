"""The exit codes every ``amoeba`` subcommand shares (slices 222 to 229)."""

from __future__ import annotations

from typing import Final

#: Exit codes, shared by every subcommand.
EXIT_OK: Final = 0  # the operation succeeded (for add and rm: applied or unchanged)
EXIT_REJECTED: Final = 1  # the operation refused the request; the result says why
EXIT_USAGE: Final = 2  # bad arguments, or a request that cannot be read
EXIT_ERROR: Final = 3  # config, home, Context Forge or store failure
