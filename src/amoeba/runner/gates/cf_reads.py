"""The Runner's reads of Context Forge for the gates: status and config (slice 128).

Each read runs in the step's checkout, because CF chooses a worktree by working
directory, through 122's injected :class:`CfRun` under the bounded runner and the tick
budget. A read that cannot give a usable answer is a :class:`ReadFailure` naming the
command and why, never a default: the caller escalates (D2, D11). ``None`` means the
tick budget refused the call.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Final, cast

from amoeba.runner.budget import TickBudget
from amoeba.runner.cf_call import CfCallFailed, CfRun, output_head, run_cf
from amoeba.runner.lifecycle.plan_read import (
    CF_KEY_INTEGRATION_BRANCH,
    CF_STATUS_COMMAND,
    CF_WORKTREE_FLAG,
    cf_argv,
    config_get_command,
)

#: The target when ``git.integration_branch`` is empty: the key's own description says
#: "Empty means no integration branch — work branches fork from and merge into main".
DEFAULT_TARGET_BRANCH: Final = "main"

_VALUE_KEY: Final = "value"


@dataclass(frozen=True)
class ReadFailure:
    """A CF read gave no usable answer; ``detail`` names the command and why."""

    detail: str


def _read_json(
    command: tuple[str, ...],
    checkout: Path,
    cf_project_id: str,
    budget: TickBudget,
    run: CfRun,
    timeout_seconds: float,
    worktree_id: str | None = None,
) -> dict[str, object] | ReadFailure | None:
    """Run ``command`` in ``checkout`` and parse a JSON object from its stdout."""
    if not budget.allows_call():
        return None
    argv = cf_argv(command, cf_project_id)
    if worktree_id is not None:
        argv += [CF_WORKTREE_FLAG, worktree_id]
    shown = " ".join(argv)
    completed = run_cf(argv, partial(run, cwd=checkout), timeout_seconds)
    if isinstance(completed, CfCallFailed):
        return ReadFailure(completed.detail)
    head = output_head(completed)
    if completed.returncode != 0:
        return ReadFailure(f"`{shown}` exited {completed.returncode}: {head}")
    try:
        parsed: object = json.loads(completed.stdout)
    except json.JSONDecodeError:
        # Expected: CF printed something else. Reported, never guessed at.
        return ReadFailure(f"`{shown}` printed no JSON: {head!r}")
    if not isinstance(parsed, dict):
        return ReadFailure(f"`{shown}` did not print a JSON object: {head!r}")
    return cast("dict[str, object]", parsed)


def read_gate(
    checkout: Path,
    worktree_id: str | None,
    cf_project_id: str,
    budget: TickBudget,
    run: CfRun,
    timeout_seconds: float,
) -> dict[str, object] | ReadFailure | None:
    """``cf status --json`` for the checkout's worktree: the document, unparsed."""
    return _read_json(
        CF_STATUS_COMMAND,
        checkout,
        cf_project_id,
        budget,
        run,
        timeout_seconds,
        worktree_id,
    )


def read_config(
    key: str,
    checkout: Path,
    cf_project_id: str,
    budget: TickBudget,
    run: CfRun,
    timeout_seconds: float,
) -> str | ReadFailure | None:
    """The string value of one CF config key as the checkout sees it.

    An answer without a string ``value`` is a failure: the key's absence is not an
    empty value.
    """
    document = _read_json(
        config_get_command(key),
        checkout,
        cf_project_id,
        budget,
        run,
        timeout_seconds,
    )
    if document is None or isinstance(document, ReadFailure):
        return document
    value = document.get(_VALUE_KEY)
    if not isinstance(value, str):
        return ReadFailure(f"`cf config get {key}` answered without a string value")
    return value


def read_target(
    checkout: Path,
    cf_project_id: str,
    budget: TickBudget,
    run: CfRun,
    timeout_seconds: float,
) -> str | ReadFailure | None:
    """The target branch: ``git.integration_branch``, or the default when empty."""
    value = read_config(
        CF_KEY_INTEGRATION_BRANCH,
        checkout,
        cf_project_id,
        budget,
        run,
        timeout_seconds,
    )
    if isinstance(value, str) and value.strip() == "":
        return DEFAULT_TARGET_BRANCH
    return value
