"""The client part's read of the machine's runs (slice 261, D11).

``status``, and ``list`` with no subject, need five facts from the machine they run
on: the ``sq runs list`` listing, each run's directory's Context Forge project, a paused
run's run file, the calls log, and (in the close sweep) whether a run missing from the
listing still has a run file. :func:`gather_runs` makes the first four and returns a
:class:`RunsDocument`; the hub part reads that and no disk. This is client-part code (it
runs ``cf`` and ``sq`` and reads files), so the hub never imports it.

Time: the listing is one ``sq`` call with its own timeout. The directory lookups are one
``cf get`` per distinct directory and share :data:`RUNS_GATHER_SECONDS`; once that is
spent each directory not yet looked up is recorded as a failed lookup that says so, so a
paused run there shows as unplaced, as a failed lookup does.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Final

from amoeba.config.home import ANSWERING_DIR_NAME
from amoeba.operations.calls_log import CallEntry, last_calls
from amoeba.operations.deps import Deps, ListRuns
from amoeba.operations.runs_document import (
    CallLine,
    CompletedRun,
    LookupKind,
    OpenRun,
    RunCheckpoint,
    RunFileFacts,
    RunLookup,
    RunsDocument,
    build_runs_document,
    listing_problem_document,
)
from amoeba.upstream.context_forge.cli_call import CfCallFailed, CfRun
from amoeba.upstream.context_forge.project_of import (
    CFProject,
    CFProjectNotFound,
    project_of,
)
from amoeba.upstream.squadron.run_file import RunFacts, RunFileProblem, read_run_facts
from amoeba.upstream.squadron.run_list import (
    ListedCheckpoint,
    ListedRun,
    RunListProblem,
)

#: Shared by every ``cf get`` the gather makes (the listing has its own timeout).
RUNS_GATHER_SECONDS: Final = 60.0

type Lookup = CFProject | CFProjectNotFound | CfCallFailed


def gather_runs(  # noqa: PLR0913 - the edges the gather reads, each a value
    *,
    list_runs: ListRuns,
    run: CfRun,
    runs_dir: Path,
    calls_dir: Path,
    scratch_dirs: Sequence[Path],
    clock: Callable[[], float],
) -> RunsDocument:
    """Read the machine's runs.

    ``clock`` is a monotonic clock in seconds, for the time limit on the lookups.
    ``scratch_dirs`` are the answering scratch roots: a run in one is left out.
    """
    listed = list_runs()
    if isinstance(listed, RunListProblem):
        return listing_problem_document(listed.reason)
    open_items = [
        item
        for item in listed
        if not item.is_completed and not _is_scratch(item, scratch_dirs)
    ]
    paused_items = [item for item in open_items if item.is_paused]
    other_items = [item for item in open_items if not item.is_paused]
    found = last_calls(calls_dir, [item.run_id for item in paused_items])
    lookups = _Lookups(run, clock)
    # Paused runs first, so a spent gather time costs the runs that matter least.
    paused = [
        _paused_run(item, lookups, runs_dir, found.entries.get(item.run_id))
        for item in paused_items
    ]
    other = [_open_run(item, lookups) for item in other_items]
    completed = [
        CompletedRun(run_id=item.run_id, status=item.status)
        for item in listed
        if item.is_completed
    ]
    return build_runs_document(
        paused=paused,
        other_open=other,
        completed=completed,
        call_problems=tuple(dict.fromkeys(found.problems)),
    )


def scratch_roots(answering_dir: Path, legacy_home: Path | None) -> tuple[Path, ...]:
    """The directories whose runs are answering scratch: the answering directory and,
    for a paused answering run started before the state move, the legacy one (D12)."""
    if legacy_home is None:
        return (answering_dir,)
    return (answering_dir, legacy_home / ANSWERING_DIR_NAME)


def gather_machine_runs(deps: Deps) -> RunsDocument:
    """The runs of this machine through the edges ``deps`` holds."""
    return gather_runs(
        list_runs=deps.list_runs,
        run=deps.cf_run,
        runs_dir=deps.squadron_runs_dir,
        calls_dir=deps.calls_log_dir,
        scratch_dirs=scratch_roots(deps.answering_dir, deps.legacy_home),
        clock=time.monotonic,
    )


def _is_scratch(item: ListedRun, scratch_dirs: Sequence[Path]) -> bool:
    """Whether the run started in an answering scratch directory (never listed)."""
    directory = item.working_directory
    if directory is None or not directory.exists():
        return False
    resolved = directory.resolve()
    return any(resolved.is_relative_to(root.resolve()) for root in scratch_dirs)


class _Lookups:
    """One ``cf get`` per distinct directory, sharing the gather's time."""

    def __init__(self, run: CfRun, clock: Callable[[], float]) -> None:
        self._run = run
        self._clock = clock
        self._started = clock()
        self._found: dict[Path, RunLookup] = {}

    def of(self, directory: Path | None) -> RunLookup:
        if directory is None:
            return RunLookup(kind=LookupKind.NO_DIRECTORY)
        if not directory.exists():
            return RunLookup(kind=LookupKind.DIRECTORY_MISSING)
        if directory not in self._found:
            self._found[directory] = self._look(directory)
        return self._found[directory]

    def _look(self, directory: Path) -> RunLookup:
        if self._clock() - self._started >= RUNS_GATHER_SECONDS:
            return RunLookup(
                kind=LookupKind.FAILED,
                detail=(
                    f"the {RUNS_GATHER_SECONDS:g} s allowed for looking up run "
                    "directories ran out before this one"
                ),
            )
        outcome = project_of(directory=directory, run=self._run)
        return _lookup_of(outcome)


def _lookup_of(outcome: Lookup) -> RunLookup:
    if isinstance(outcome, CFProject):
        return RunLookup(kind=LookupKind.PROJECT, project_id=outcome.id)
    if isinstance(outcome, CFProjectNotFound):
        return RunLookup(kind=LookupKind.NOT_A_PROJECT, detail=outcome.message)
    return RunLookup(kind=LookupKind.FAILED, detail=outcome.detail)


def _checkpoint_of(checkpoint: ListedCheckpoint | None) -> RunCheckpoint | None:
    if checkpoint is None:
        return None
    return RunCheckpoint(
        kind=checkpoint.kind,
        paused_at=checkpoint.paused_at,
        question=checkpoint.question,
    )


def _open_run(item: ListedRun, lookups: _Lookups) -> OpenRun:
    directory = item.working_directory
    return OpenRun(
        run_id=item.run_id,
        pipeline=item.pipeline,
        status=item.status,
        working_directory=None if directory is None else str(directory),
        checkpoint=_checkpoint_of(item.checkpoint),
        lookup=lookups.of(directory),
    )


def _paused_run(
    item: ListedRun, lookups: _Lookups, runs_dir: Path, last: CallEntry | None
) -> OpenRun:
    """The run with its run file's facts (or why not) and its newest calls-log line."""
    base = _open_run(item, lookups)
    read = read_run_facts(runs_dir, item.run_id)
    call = None if last is None else _call_line(last)
    if isinstance(read, RunFileProblem):
        return base.model_copy(
            update={"run_file_problem": read.reason, "last_call": call}
        )
    return base.model_copy(update={"run_file": _facts_of(read), "last_call": call})


def _facts_of(facts: RunFacts) -> RunFileFacts:
    directory = facts.working_directory
    return RunFileFacts(
        params=dict(facts.params),
        execution_mode=facts.execution_mode.value,
        working_directory=None if directory is None else str(directory),
    )


def _call_line(entry: CallEntry) -> CallLine:
    return CallLine(
        at=entry.at,
        directory=entry.directory,
        outcome=entry.outcome,
        reason=entry.reason,
        error=entry.error,
        detail=entry.detail,
    )
