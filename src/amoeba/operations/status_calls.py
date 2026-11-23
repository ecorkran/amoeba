"""``last_call`` on the runs ``status`` shows as a missed hook (slice 228, D11, D12).

A run classed ``unhandled`` or ``claim_stale`` is one the hook should have handled.
The newest calls-log line for it says whether the hook ran and why it did nothing. The
lines come from the ``runs`` document, which holds one for every paused run that has one
(261 D11); this module reads no disk.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from amoeba.operations.calls_log import CallEntry
from amoeba.operations.pause_class import PauseClass
from amoeba.operations.runs_document import CallLine, RunsDocument
from amoeba.operations.status_runs import MemberRun

#: The classes where a missed hook is the question ``last_call`` answers.
#: A held run is in it too: a failed start or a failed child shows here (242 D9).
MISSED_HOOK_CLASSES = frozenset(
    {PauseClass.UNHANDLED, PauseClass.CLAIM_STALE, PauseClass.WAITING_ON_REQUEST}
)


@dataclass(frozen=True)
class RunsWithCalls:
    """The runs with ``last_call`` set where it applies, and the read problems."""

    runs: list[MemberRun]
    problems: tuple[str, ...]


def attach_last_calls(runs: list[MemberRun], document: RunsDocument) -> RunsWithCalls:
    """``runs`` with each missed-hook run's newest calls-log line attached.

    The document's read problems (an unreadable day file, a bad line) are listed once
    each.
    """
    lines = {run.run_id: run.last_call for run in document.open_runs}
    attached: list[MemberRun] = []
    for item in runs:
        line = lines.get(item.entry.run_id)
        if item.entry.pause in MISSED_HOOK_CLASSES and line is not None:
            entry = item.entry.model_copy(
                update={"last_call": _call_entry(item.entry.run_id, line)}
            )
            item = replace(item, entry=entry)
        attached.append(item)
    return RunsWithCalls(attached, tuple(dict.fromkeys(document.call_problems)))


def _call_entry(run_id: str, line: CallLine) -> CallEntry:
    return CallEntry(
        at=line.at,
        run_id=run_id,
        directory=line.directory,
        outcome=line.outcome,
        reason=line.reason,
        error=line.error,
        detail=line.detail,
    )
