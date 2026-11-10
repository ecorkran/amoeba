"""Run the two plan reads: ``cf list initiatives`` and ``cf list slices`` (slice 223).

Parsing is ``plan``'s; the command words are ``target_read``'s; running is
``cli_call``'s. This module joins them for a checkout: each read gives the parsed
value, CF's own ``error: true`` document where that is an expected answer, or a
:class:`ReadFailure` (never a guess) when CF gave nothing usable.
"""

from __future__ import annotations

from functools import partial
from pathlib import Path

from amoeba.upstream.context_forge.cli_call import (
    CfCallFailed,
    CfRun,
    output_head,
    run_cf,
)
from amoeba.upstream.context_forge.plan import (
    CFErrorDocument,
    CFInitiative,
    CFSliceList,
    PlanParseError,
    parse_initiatives,
    parse_slice_list,
)
from amoeba.upstream.context_forge.target_read import (
    ReadFailure,
    cf_argv,
    list_initiatives_command,
    list_slices_command,
)


def read_initiatives(
    checkout: Path, cf_project_id: str, run: CfRun, timeout_seconds: float
) -> list[CFInitiative] | ReadFailure:
    """Every initiative of the project, as the checkout sees it."""
    argv = cf_argv(list_initiatives_command(), cf_project_id)
    shown = " ".join(argv)
    completed = run_cf(argv, partial(run, cwd=checkout), timeout_seconds)
    if isinstance(completed, CfCallFailed):
        return ReadFailure(completed.detail)
    if completed.returncode != 0:
        return ReadFailure(
            f"`{shown}` exited {completed.returncode}: {output_head(completed)}"
        )
    try:
        return parse_initiatives(completed.stdout)
    except PlanParseError as error:
        return ReadFailure(f"`{shown}` gave an unusable list: {error}")


def read_slice_list(
    checkout: Path,
    cf_project_id: str,
    initiative_index: int,
    run: CfRun,
    timeout_seconds: float,
) -> CFSliceList | CFErrorDocument | ReadFailure:
    """One initiative's slice plan, or CF's error document when it has none.

    CF prints that document on stderr with exit 1, so a failing call is read as
    the document first; anything else that fails is a :class:`ReadFailure`.
    """
    argv = cf_argv(list_slices_command(initiative_index), cf_project_id)
    shown = " ".join(argv)
    completed = run_cf(argv, partial(run, cwd=checkout), timeout_seconds)
    if isinstance(completed, CfCallFailed):
        return ReadFailure(completed.detail)
    text = completed.stdout if completed.returncode == 0 else completed.stderr
    try:
        parsed = parse_slice_list(text)
    except PlanParseError as error:
        return ReadFailure(
            f"`{shown}` exited {completed.returncode} with an unusable answer: "
            f"{output_head(completed)} ({error})"
        )
    if completed.returncode != 0 and not isinstance(parsed, CFErrorDocument):
        return ReadFailure(
            f"`{shown}` exited {completed.returncode}: {output_head(completed)}"
        )
    return parsed
