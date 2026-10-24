"""The ``cf`` commands the Runner runs, spelled once (D11), and one link's plan read.

The shape probes in ``probes.py`` and the plan read both import the commands, so a
command cannot be probed in one form and read in another.

:func:`read_plan` reads one CF link: the initiatives, then each initiative's slice
list, every call a separate subprocess that checks the :class:`TickBudget` first
(D7). Expected CF failures are answers (:class:`SliceReadFailed`,
:class:`PlanReadFailed`, :class:`NoSlicePlan`), never exceptions, and a read is
never retried within the tick. CF writes the ``error: true`` document for an
initiative without a slice plan to stderr, so a non-zero exit is classified from
both streams; the decision never reads the error's ``message`` (D8).
"""

from __future__ import annotations

import subprocess
from collections.abc import Collection, Sequence
from dataclasses import dataclass
from typing import Final

from amoeba.runner.budget import TickBudget
from amoeba.runner.cf_call import CfCallFailed, CfRun, output_head, run_cf
from amoeba.upstream.context_forge import (
    CFErrorDocument,
    CFInitiative,
    CFSliceList,
    PlanParseError,
    parse_initiatives,
    parse_slice_list,
)

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


#: ``cf set -p <id> slice <index>``: the pointer write (slice 125, D2).
CF_SET_COMMAND: Final = "set"
CF_SET_FIELD_SLICE: Final = "slice"


def set_slice_argv(cf_project_id: str, slice_index: int) -> list[str]:
    """The full argument vector pointing a checkout's CF at a slice."""
    return [
        CF_EXECUTABLE,
        CF_SET_COMMAND,
        CF_PROJECT_FLAG,
        cf_project_id,
        CF_SET_FIELD_SLICE,
        str(slice_index),
    ]


def cf_argv(command: Sequence[str], cf_project_id: str) -> list[str]:
    """The full argument vector: executable, command, then ``-p <id>``."""
    return [CF_EXECUTABLE, *command, CF_PROJECT_FLAG, cf_project_id]


@dataclass(frozen=True)
class NoSlicePlan:
    """CF has no slice plan for the initiative, and no slice nodes are linked to it."""


@dataclass(frozen=True)
class SliceReadFailed:
    """The initiative's slice list is unavailable; ``detail`` names the command."""

    detail: str


type SliceRead = CFSliceList | NoSlicePlan | SliceReadFailed


@dataclass(frozen=True)
class PlanRead:
    """A complete read: every initiative, and the answer for each one's slices."""

    initiatives: tuple[CFInitiative, ...]
    slices: dict[int, SliceRead]


@dataclass(frozen=True)
class PlanReadFailed:
    """The initiatives read failed; nothing is applied for the link."""

    detail: str


@dataclass(frozen=True)
class PlanReadCutOff:
    """The budget refused a call. Nothing is applied; the link is due again."""


type PlanReadResult = PlanRead | PlanReadFailed | PlanReadCutOff


def read_plan(
    cf_project_id: str,
    linked_slice_initiatives: Collection[int],
    run: CfRun,
    budget: TickBudget,
    timeout_seconds: float,
) -> PlanReadResult:
    """Read one link's plan under the tick budget.

    Args:
        cf_project_id: The linked CF project.
        linked_slice_initiatives: Indexes of initiatives that already have linked
            slice nodes. An error document for one of them is a failed read, not
            the normal no-plan state.
        run: Runs ``cf``.
        budget: Checked before every call; a refusal returns :class:`PlanReadCutOff`.
        timeout_seconds: The longest one call may run.
    """
    if not budget.allows_call():
        return PlanReadCutOff()
    initiatives = _read_initiatives(cf_project_id, run, timeout_seconds)
    if isinstance(initiatives, PlanReadFailed):
        return initiatives

    slices: dict[int, SliceRead] = {}
    for initiative in initiatives:
        if not budget.allows_call():
            return PlanReadCutOff()
        slices[initiative.index] = _read_slice_list(
            cf_project_id,
            initiative.index,
            initiative.index in linked_slice_initiatives,
            run,
            timeout_seconds,
        )
    return PlanRead(tuple(initiatives), slices)


def _read_initiatives(
    cf_project_id: str, run: CfRun, timeout_seconds: float
) -> list[CFInitiative] | PlanReadFailed:
    argv = cf_argv(CF_INITIATIVES_COMMAND, cf_project_id)
    shown = " ".join(argv)
    completed = run_cf(argv, run, timeout_seconds)
    if isinstance(completed, CfCallFailed):
        return PlanReadFailed(completed.detail)
    if completed.returncode != 0:
        return PlanReadFailed(
            f"`{shown}` exited {completed.returncode}: {output_head(completed)}"
        )
    try:
        return parse_initiatives(completed.stdout)
    except PlanParseError as error:
        # Specific: CF printed something the plan model rejects. Answered, not raised.
        return PlanReadFailed(
            f"`{shown}` {_one_line(error)}: {output_head(completed)!r}"
        )


def _read_slice_list(
    cf_project_id: str,
    initiative_index: int,
    has_linked_slices: bool,
    run: CfRun,
    timeout_seconds: float,
) -> SliceRead:
    argv = cf_argv(slice_list_command(initiative_index), cf_project_id)
    shown = " ".join(argv)
    completed = run_cf(argv, run, timeout_seconds)
    if isinstance(completed, CfCallFailed):
        return SliceReadFailed(completed.detail)

    parsed = _first_parsed(completed)
    if isinstance(parsed, CFErrorDocument):
        if has_linked_slices:
            return SliceReadFailed(
                f"`{shown}` reported an error for an initiative with linked slices"
            )
        return NoSlicePlan()
    if completed.returncode != 0:
        return SliceReadFailed(
            f"`{shown}` exited {completed.returncode}: {output_head(completed)}"
        )
    if parsed is None:
        return SliceReadFailed(
            f"`{shown}` printed no usable slice list: {output_head(completed)!r}"
        )
    return parsed


def _first_parsed(
    completed: subprocess.CompletedProcess[str],
) -> CFSliceList | CFErrorDocument | None:
    """The slice list or error document on stdout, else on stderr; else ``None``.

    CF prints the error document on stderr with an empty stdout, so both streams
    are tried, stdout first.
    """
    for text in (completed.stdout, completed.stderr):
        try:
            return parse_slice_list(text)
        except PlanParseError:
            # Specific: this stream holds no slice document; try the other one.
            continue
    return None


def _one_line(error: PlanParseError) -> str:
    return " ".join(str(error).split())
