"""``last_call`` on the runs ``status`` shows as a missed hook (slice 228, D11, D12).

A run classed ``unhandled`` or ``claim_stale`` is one the hook should have handled.
The newest calls-log line for it says whether the hook ran and why it did nothing.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

from amoeba.operations.calls_log import last_calls
from amoeba.operations.pause_class import PauseClass
from amoeba.operations.status_runs import MemberRun

#: The classes where a missed hook is the question ``last_call`` answers.
MISSED_HOOK_CLASSES = frozenset({PauseClass.UNHANDLED, PauseClass.CLAIM_STALE})


@dataclass(frozen=True)
class RunsWithCalls:
    """The runs with ``last_call`` set where it applies, and the read problems."""

    runs: list[MemberRun]
    problems: tuple[str, ...]


def attach_last_calls(runs: list[MemberRun], log_dir: Path) -> RunsWithCalls:
    """``runs`` with each missed-hook run's newest calls-log line attached.

    Read problems (an unreadable day file, a bad line) are listed once each.
    """
    wanted = {
        item.entry.run_id for item in runs if item.entry.pause in MISSED_HOOK_CLASSES
    }
    found = last_calls(log_dir, wanted)
    attached = [
        replace(
            item,
            entry=item.entry.model_copy(
                update={"last_call": found.entries.get(item.entry.run_id)}
            ),
        )
        if item.entry.run_id in wanted
        else item
        for item in runs
    ]
    return RunsWithCalls(attached, tuple(dict.fromkeys(found.problems)))
