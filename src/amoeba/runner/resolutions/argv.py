"""The ``sq run --resume`` command line (slice 127, D4).

Pure. The instructions are one argv element, byte for byte: they go to a process
without a shell, so spaces, quotes and newlines need no escaping. A resume names the
run it continues and nothing else: no pipeline, no ``-p``, no ``--run-id``.

Checked against the real ``sq`` (squadron 0.24.5): a value that starts with ``-``,
even ``--decision accept``, is read as the instructions text, not as an option.
"""

from __future__ import annotations

from typing import Final

from amoeba.process import SQ_EXECUTABLE
from amoeba.runner.launch import SQ_RUN_COMMAND
from amoeba.runner.resolutions.vocabulary import Continuation

RESUME_FLAG: Final = "--resume"
DECISION_FLAG: Final = "--decision"
INSTRUCTIONS_FLAG: Final = "--instructions"


def resume_argv(
    run_id: str, decision: Continuation, instructions: str | None
) -> list[str]:
    """``sq run --resume <run_id> --decision <d> [--instructions <text>]``.

    Raises:
        ValueError: If ``decision`` is ``observe``, which resumes nothing.
    """
    if decision is Continuation.OBSERVE:
        raise ValueError("an observe continuation has no resume command")
    argv = [SQ_EXECUTABLE, SQ_RUN_COMMAND, RESUME_FLAG, run_id]
    argv += [DECISION_FLAG, decision.value]
    if instructions is not None:
        argv += [INSTRUCTIONS_FLAG, instructions]
    return argv
