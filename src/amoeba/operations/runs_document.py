"""The machine's Squadron runs, as plain values and as the document that travels
(slice 261, D11).

The client part (``operations.run_gather``) reads ``sq runs list``, each run's
directory, a paused run's run file and the calls log, and builds a
:class:`RunsDocument`. The hub part of ``status`` and ``list`` parses it back with
:func:`parse_runs` and reads no disk. Everything here is plain data: this module
imports nothing from ``upstream``, so the hub reaches it without reaching the code that
runs ``cf`` or ``sq``.

Size: the document is built paused runs first, then other runs that are not completed,
then completed ones, and a run is added only while the encoded document stays under
:data:`RUNS_DOCUMENT_MAX_BYTES`. What does not fit is counted per kind.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Final

from pydantic import BaseModel, ConfigDict, ValidationError

from amoeba.operations.errors import MALFORMED_CALL, CallRefused

#: Under the door's 1 MiB body limit (260), leaving room for the rest of the body.
RUNS_DOCUMENT_MAX_BYTES: Final = 768 * 1024
#: The body key the document travels under (``wire.protocol`` names it as well).
RUNS_KEY: Final = "runs"
#: Squadron's listing statuses the hub part needs by name (a test pins these against
#: ``upstream.squadron.run_list``, which this module may not import).
PAUSED_STATUS: Final = "paused"
#: Room kept for the counts and the problem texts the builder adds after the runs.
_TAIL_ALLOWANCE_BYTES: Final = 4096
#: The comma between two array elements.
_SEPARATOR_BYTES: Final = 1


class _Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class LookupKind(StrEnum):
    """What the client found when it asked about a run's directory."""

    NO_DIRECTORY = "no_directory"
    DIRECTORY_MISSING = "directory_missing"
    PROJECT = "project"
    NOT_A_PROJECT = "not_a_project"
    FAILED = "failed"


class RunLookup(_Frozen):
    """The directory lookup: the project id for ``project``, the text for ``failed``."""

    kind: LookupKind
    project_id: str | None = None
    detail: str | None = None


class RunCheckpoint(_Frozen):
    """The parts of the listing's checkpoint that are used; ``kind`` is raw text."""

    kind: str | None
    paused_at: str | None
    question: str | None


class RunFileFacts(_Frozen):
    """What a paused run's run file says."""

    params: dict[str, str]
    #: Squadron's execution mode text (``sdk`` or ``prompt-only``).
    execution_mode: str
    working_directory: str | None


class CallLine(_Frozen):
    """The newest calls-log line for a run; times are the calling machine's."""

    at: datetime
    directory: str
    outcome: str | None
    reason: str | None
    error: str | None
    detail: str | None


class OpenRun(_Frozen):
    """A run that is not completed, as the listing gave it, and what was read for it."""

    run_id: str
    pipeline: str
    #: Squadron's status text, raw.
    status: str
    working_directory: str | None
    checkpoint: RunCheckpoint | None
    lookup: RunLookup
    #: Paused runs only: the run file's facts, or why they could not be read.
    run_file: RunFileFacts | None = None
    run_file_problem: str | None = None
    #: Paused runs only: the newest calls-log line, if the log has one.
    last_call: CallLine | None = None

    @property
    def is_paused(self) -> bool:
        return self.status == PAUSED_STATUS


class CompletedRun(_Frozen):
    """A finished run: all the close sweep needs."""

    run_id: str
    status: str


class LeftOut(_Frozen):
    """How many runs of each kind did not fit under the size limit."""

    paused: int = 0
    open: int = 0
    completed: int = 0

    @property
    def total(self) -> int:
        return self.paused + self.open + self.completed


class RunsDocument(_Frozen):
    """The machine's runs, or in place of them the listing's problem text."""

    #: Set when ``sq runs list`` could not be read; every other field is then empty.
    listing_problem: str | None = None
    open_runs: tuple[OpenRun, ...] = ()
    completed_runs: tuple[CompletedRun, ...] = ()
    left_out: LeftOut = LeftOut()
    #: Calls-log read problems, once each.
    call_problems: tuple[str, ...] = ()


@dataclass(frozen=True)
class RunStanding:
    """Where a run is, as the close sweep and the waiting entries read it."""

    status: str
    is_paused: bool
    #: Whether the listing gave the run a checkpoint.
    has_checkpoint: bool
    paused_at: str | None


def standings(document: RunsDocument) -> dict[str, RunStanding]:
    """Every run the document holds, open or completed, by run id."""
    found = {
        run.run_id: RunStanding(
            status=run.status,
            is_paused=run.is_paused,
            has_checkpoint=run.checkpoint is not None,
            paused_at=None if run.checkpoint is None else run.checkpoint.paused_at,
        )
        for run in document.open_runs
    }
    for finished in document.completed_runs:
        found[finished.run_id] = RunStanding(
            status=finished.status,
            is_paused=False,
            has_checkpoint=False,
            paused_at=None,
        )
    return found


def left_out_text(left_out: LeftOut) -> str | None:
    """The sentence for a cut document (a ``file_problems`` entry), or ``None``."""
    parts = [
        f"{count} {kind}"
        for count, kind in (
            (left_out.paused, "paused"),
            (left_out.open, "other open"),
            (left_out.completed, "completed"),
        )
        if count
    ]
    if not parts:
        return None
    return (
        f"the runs document was cut at {RUNS_DOCUMENT_MAX_BYTES} bytes: "
        f"{', '.join(parts)} runs are not shown"
    )


def listing_problem_document(reason: str) -> RunsDocument:
    """The document that says the listing could not be read."""
    return RunsDocument(listing_problem=reason)


def _encoded_bytes(item: BaseModel) -> int:
    return len(item.model_dump_json().encode("utf-8")) + _SEPARATOR_BYTES


def build_runs_document(
    *,
    paused: Sequence[OpenRun],
    other_open: Sequence[OpenRun],
    completed: Sequence[CompletedRun],
    call_problems: Sequence[str],
    max_bytes: int = RUNS_DOCUMENT_MAX_BYTES,
) -> RunsDocument:
    """The document holding as many runs as fit, paused first, with the rest counted.

    Once a run does not fit, nothing after it is added, so a lower kind never takes
    room a higher kind needed.
    """
    problems = tuple(call_problems)
    budget = (
        max_bytes
        - _TAIL_ALLOWANCE_BYTES
        - sum(len(text.encode("utf-8")) + _SEPARATOR_BYTES for text in problems)
    )
    kept_paused, left_paused, budget = _fit(paused, budget)
    kept_other, left_other, budget = _fit(other_open, budget)
    kept_completed, left_completed, _ = _fit(completed, budget)
    return RunsDocument(
        open_runs=(*kept_paused, *kept_other),
        completed_runs=tuple(kept_completed),
        left_out=LeftOut(paused=left_paused, open=left_other, completed=left_completed),
        call_problems=problems,
    )


def _fit[Item: BaseModel](
    items: Sequence[Item], budget: int
) -> tuple[list[Item], int, int]:
    """The leading ``items`` that fit in ``budget``, how many did not, and the room left
    (none once an item has been cut)."""
    kept: list[Item] = []
    for item in items:
        size = _encoded_bytes(item)
        if size > budget:
            return kept, len(items) - len(kept), 0
        kept.append(item)
        budget -= size
    return kept, 0, budget


def runs_to_document(value: RunsDocument) -> dict[str, object]:
    """The JSON-ready document for the body's ``runs`` key."""
    return value.model_dump(mode="json")


def parse_runs(value: object) -> RunsDocument:
    """The runs document in ``value``.

    Raises:
        CallRefused: ``malformed_call`` when the value is missing or is not a runs
            document; the message names the key and the fields, never a value.
    """
    if not isinstance(value, dict):
        raise CallRefused(MALFORMED_CALL, f"{RUNS_KEY} is missing or is not an object")
    try:
        return RunsDocument.model_validate(value)
    except ValidationError as error:
        parts = [
            f"{RUNS_KEY}.{'.'.join(str(step) for step in problem['loc'])}: "
            f"{problem['type']}"
            for problem in error.errors()
        ]
        raise CallRefused(
            MALFORMED_CALL, f"{RUNS_KEY} is not usable: {'; '.join(parts)}"
        ) from error
