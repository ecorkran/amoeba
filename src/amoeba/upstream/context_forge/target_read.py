"""The ``cf`` commands spelled once, and the read of a checkout's target branch.

``cf config get git.integration_branch`` run in a checkout says which branch work
merges into; the answering sources are read at that branch's commit. CF chooses a
worktree by working directory, so the read runs in the checkout.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Final, cast

from amoeba.upstream.context_forge.cli_call import (
    OUTPUT_HEAD_CHARS,
    CfCallFailed,
    CfRun,
    output_head,
    run_cf,
)

CF_EXECUTABLE: Final = "cf"
CF_PROJECT_FLAG: Final = "-p"
CF_JSON_FLAG: Final = "--json"

#: The CF config key naming the integration branch.
CF_KEY_INTEGRATION_BRANCH: Final = "git.integration_branch"

#: The target when ``git.integration_branch`` is empty: the key's own description says
#: "Empty means no integration branch — work branches fork from and merge into main".
DEFAULT_TARGET_BRANCH: Final = "main"

_VALUE_KEY: Final = "value"


def config_get_command(key: str) -> tuple[str, ...]:
    """``cf config get <key> --json``, run in a checkout."""
    return ("config", "get", key, CF_JSON_FLAG)


def cf_argv(command: Sequence[str], cf_project_id: str) -> list[str]:
    """The full argument vector: executable, command, then ``-p <id>``."""
    return [CF_EXECUTABLE, *command, CF_PROJECT_FLAG, cf_project_id]


@dataclass(frozen=True)
class ReadFailure:
    """A CF read gave no usable answer; ``detail`` names the command and why."""

    detail: str


def read_config(
    key: str,
    checkout: Path,
    cf_project_id: str,
    run: CfRun,
    timeout_seconds: float,
) -> str | ReadFailure:
    """The string value of one CF config key as the checkout sees it.

    A read that cannot give a string ``value`` is a failure, never a default; the
    key's absence is not an empty value.
    """
    argv = cf_argv(config_get_command(key), cf_project_id)
    shown = " ".join(argv)
    completed = run_cf(argv, partial(run, cwd=checkout), timeout_seconds)
    if isinstance(completed, CfCallFailed):
        return ReadFailure(completed.detail)
    if completed.returncode != 0:
        head = output_head(completed)
        return ReadFailure(f"`{shown}` exited {completed.returncode}: {head}")
    head = completed.stdout[:OUTPUT_HEAD_CHARS]
    try:
        document: object = json.loads(completed.stdout)
    except json.JSONDecodeError:
        # Expected: CF printed something else. Reported, never guessed at.
        return ReadFailure(f"`{shown}` printed no JSON: {head!r}")
    if not isinstance(document, dict):
        return ReadFailure(f"`{shown}` did not print a JSON object: {head!r}")
    value = cast("dict[str, object]", document).get(_VALUE_KEY)
    if not isinstance(value, str):
        return ReadFailure(f"`{shown}` answered without a string value")
    return value


def read_target(
    checkout: Path, cf_project_id: str, run: CfRun, timeout_seconds: float
) -> str | ReadFailure:
    """The target branch: ``git.integration_branch``, or the default when empty."""
    value = read_config(
        CF_KEY_INTEGRATION_BRANCH, checkout, cf_project_id, run, timeout_seconds
    )
    if isinstance(value, str) and value.strip() == "":
        return DEFAULT_TARGET_BRANCH
    return value
