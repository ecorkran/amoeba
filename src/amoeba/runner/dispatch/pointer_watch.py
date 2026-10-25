"""Has someone moved the CF pointer away from a step with a run in flight? (D11)

The Runner writes a pointer only into a free checkout, so its own writes never move a
pointer away from a run; and Squadron's own ``cf set slice`` during the run writes the
same index. So any other index, in the snapshot taken after the run's pointer write
resolved, is someone else's move. No ``cf_updated_at`` matching is needed.

Pure: :func:`pointer_moved` reads only the values it is given. :func:`watched_runs`
is the store read that builds them.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime

from amoeba.process import CF_FIELD_FILE_SLICE, RESULT_WORKTREE_ID
from amoeba.runner.dispatch.checkout import is_plain_int
from amoeba.runner.faults import Fault, FaultKind, TickFaults
from amoeba.store import (
    PARAM_CONTINUATION,
    PARAM_EXPECTED_SLICE_INDEX,
    PARAM_PROJECT,
    PARAM_RUN_ID,
    CFSnapshot,
    CommandKind,
    JournalEntry,
    JournalOutcome,
    Store,
)
from amoeba.upstream.context_forge import (
    STATE_PROJECT_KEY,
    STATE_WORKTREES_KEY,
    parse_slice_stem,
)

#: The projected field holding each level's active slice.
_WORKTREE_ACTIVE_SLICE = "activeSlice"


@dataclass(frozen=True)
class WatchedRun:
    """An in-flight run and the pointer it started under."""

    node_id: str
    run_id: str
    cf_project_id: str
    #: The worktree the pointer was written in; ``None`` for a project without any.
    worktree_id: str | None
    #: The slice index the pointer was written to.
    slice_index: int
    #: When the pointer write resolved (for a continuation, when the continuation was
    #: issued): only later snapshots say anything about it.
    pointer_resolved_at: datetime


@dataclass(frozen=True)
class MovedPointer:
    """A run whose pointer now reads another slice. ``observed`` is the raw value."""

    node_id: str
    run_id: str
    worktree_id: str | None
    observed: str


def pointer_moved(
    in_flight: Sequence[WatchedRun],
    snapshots: Mapping[str, CFSnapshot | None],
) -> list[MovedPointer]:
    """The in-flight runs whose pointer reads another slice than they started under.

    ``snapshots`` is each CF project's latest observed snapshot. A snapshot observed
    no later than the pointer write resolved says nothing about it and is ignored;
    so is a worktree the snapshot does not carry, and a value that does not parse.
    """
    moved: list[MovedPointer] = []
    for run in in_flight:
        snapshot = snapshots.get(run.cf_project_id)
        if snapshot is None or snapshot.observed_at <= run.pointer_resolved_at:
            continue
        value = _active_slice(snapshot, run.worktree_id)
        stem = parse_slice_stem(value)
        if value is not None and stem is not None and stem.index != run.slice_index:
            moved.append(MovedPointer(run.node_id, run.run_id, run.worktree_id, value))
    return moved


def watched_runs(
    store: Store, project_id: str, in_flight: Sequence[JournalEntry]
) -> list[WatchedRun]:
    """The in-flight ``sq_run`` entries that started under a resolved pointer write.

    A run with no resolved pointer write on its step (one launched some other way) is
    not watched: there is no pointer to have moved. A continuation (slice 127) watches
    the step's latest pointer write too, but only snapshots after the continuation
    was issued count: a move while the run sat paused is the PM's business.
    """
    watched: list[WatchedRun] = []
    for entry in in_flight:
        pointer = _pointer_write_before(store, project_id, entry)
        run_id = entry.parameters.get(PARAM_RUN_ID)
        cf_project = pointer.parameters.get(PARAM_PROJECT) if pointer else None
        index = pointer.parameters.get(PARAM_EXPECTED_SLICE_INDEX) if pointer else None
        since = _watch_start(entry, pointer)
        if (
            pointer is None
            or since is None
            or not isinstance(run_id, str)
            or not isinstance(cf_project, str)
            or not is_plain_int(index)
        ):
            continue
        worktree = (pointer.result or {}).get(RESULT_WORKTREE_ID)
        watched.append(
            WatchedRun(
                entry.node_id,
                run_id,
                cf_project,
                worktree if isinstance(worktree, str) else None,
                index,
                since,
            )
        )
    return watched


def _watch_start(run: JournalEntry, pointer: JournalEntry | None) -> datetime | None:
    """When snapshots start to count: the pointer write, or a continuation's issue."""
    if pointer is None:
        return None
    if PARAM_CONTINUATION in run.parameters:
        return run.issued_at
    return pointer.resolved_at


def _pointer_write_before(
    store: Store, project_id: str, run: JournalEntry
) -> JournalEntry | None:
    """The latest pointer write on the run's step that landed before the run began."""
    earlier = [
        e
        for e in store.journal_entries(project_id, node_id=run.node_id)
        if e.kind is CommandKind.CF_WRITE
        and e.outcome in {JournalOutcome.COMPLETED, JournalOutcome.ADOPTED}
        and PARAM_EXPECTED_SLICE_INDEX in e.parameters
        and (
            run.issued_at is None or e.issued_at is None or e.issued_at <= run.issued_at
        )
    ]
    return earlier[-1] if earlier else None


def _active_slice(snapshot: CFSnapshot, worktree_id: str | None) -> str | None:
    """The snapshot's active slice at the worktree's level, if it states one."""
    if snapshot.state is None:
        return None
    if worktree_id is None:
        project = snapshot.state.get(STATE_PROJECT_KEY)
        return _text(project, CF_FIELD_FILE_SLICE)
    worktrees = snapshot.state.get(STATE_WORKTREES_KEY)
    if not isinstance(worktrees, Mapping):
        return None
    return _text(worktrees.get(worktree_id), _WORKTREE_ACTIVE_SLICE)  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType]


def _text(level: object, field: str) -> str | None:
    if not isinstance(level, Mapping):
        return None
    value = level.get(field)  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    return value if isinstance(value, str) else None


#: The escalation payload key listing every moved run.
PAYLOAD_RUNS = "runs"

#: Keys of each moved-run listing in that payload.
LISTING_NODE_ID = "node_id"
LISTING_RUN_ID = "run_id"
LISTING_WORKTREE_ID = "worktree_id"
LISTING_OBSERVED = "observed"


def watch_pointers(
    store: Store, project_id: str, in_flight: Sequence[JournalEntry], faults: TickFaults
) -> None:
    """Add a ``pointer_moved`` fault to ``faults`` while any in-flight run has moved.

    The fault recurs every tick the condition holds, so the project escalation stays
    open, and it closes on the first complete tick without it (122's closure rule).
    The runs are not touched: they are observed and ingested as usual (D11).
    """
    watched = watched_runs(store, project_id, in_flight)
    snapshots = {
        cf_project: store.latest_cf_snapshots(project_id, cf_project)[1]
        for cf_project in {run.cf_project_id for run in watched}
    }
    moved = pointer_moved(watched, snapshots)
    if not moved:
        return
    listing = [
        {
            LISTING_NODE_ID: m.node_id,
            LISTING_RUN_ID: m.run_id,
            LISTING_WORKTREE_ID: m.worktree_id,
            LISTING_OBSERVED: m.observed,
        }
        for m in moved
    ]
    faults.add(
        Fault(
            FaultKind.POINTER_MOVED,
            f"{len(moved)} run(s) in flight have had their CF pointer moved to "
            "another slice by someone else",
            extra={PAYLOAD_RUNS: listing},
        )
    )
