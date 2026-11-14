"""The commands the text output tells a person to run, each defined once.

Every command here is complete except for what only the person has: the answer or the
reason is a quoted ``"<...>"`` placeholder, and a project name is the bare word
``NAME``. Built from ``OperationName.cli_name`` so a renamed command changes in one
place.
"""

from __future__ import annotations

import shlex
from pathlib import Path
from typing import Final

from amoeba.operations.names import PROGRAM_NAME, OperationName
from amoeba.store.models import QuestionKey

CF_INIT_COMMAND: Final = "cf init"
ANSWER_PLACEHOLDER: Final = '"<your answer>"'
REASON_PLACEHOLDER: Final = '"<why it is closed>"'


def _command(name: OperationName, *words: str) -> str:
    return " ".join((PROGRAM_NAME, name.cli_name, *words))


def answer_command(key: QuestionKey) -> str:
    return _command(
        OperationName.ANSWER,
        shlex.quote(key.run_id),
        "--paused-at",
        shlex.quote(key.paused_at),
        "--text",
        ANSWER_PLACEHOLDER,
    )


def dismiss_command(key: QuestionKey) -> str:
    return _command(
        OperationName.DISMISS,
        shlex.quote(key.run_id),
        "--paused-at",
        shlex.quote(key.paused_at),
        "--reason",
        REASON_PLACEHOLDER,
    )


def handle_pause_command(run_id: str, directory: Path | None) -> str:
    """``handle-pause`` for a run; it must run in the run's own checkout."""
    command = _command(OperationName.HANDLE_PAUSE, shlex.quote(run_id))
    if directory is None:
        return command
    return f"cd {shlex.quote(str(directory))} && {command}"


def add_project_command() -> str:
    """``add`` aimed at a named Context Forge project, for a directory with none."""
    return _command(OperationName.ADD, "--project NAME")


def rm_member_command() -> str:
    """``rm`` aimed at a named member, for a directory with no project."""
    return _command(OperationName.RM, "NAME")


def clear_concept_command() -> str:
    return _command(OperationName.RM, "--concept")


def list_command(*, as_json: bool = False) -> str:
    return _command(OperationName.LIST, *(["--json"] if as_json else []))


def mark_read_command(through: int) -> str:
    return _command(OperationName.MARK_READ, "--through", str(through))


#: What to run when the working directory is no Context Forge project.
NOT_A_PROJECT_FIXES: Final = (CF_INIT_COMMAND, add_project_command())
