"""When a CF link's plan is read (D7): on an interval, or early on a pointer change.

Plan documents change without ``projects.json`` changing, so each link is read on
an interval. A change in the link's CF snapshot also makes it due now. State is
in memory, per ``(project, link)``, for the process lifetime: every link is due on
the first tick of a lifetime.

The same state carries the closure rule for ``plan_read_failed`` (D8): a link whose
last read failed counts as a recurrence on every tick until a read succeeds.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from amoeba.store import CFSnapshot

#: A link's latest snapshot, and its latest ``observed`` one, as
#: ``Store.latest_cf_snapshots`` returns them.
type LinkSnapshots = tuple[CFSnapshot | None, CFSnapshot | None]

type LinkKey = tuple[str, str]


@dataclass
class _LinkState:
    """What the schedule remembers about one link."""

    last_complete_at: float | None = None
    seen_snapshot_id: int | None = None
    trigger_pending: bool = False
    last_failed: bool = False


class PlanReadSchedule:
    """Which links are due for a plan read."""

    def __init__(self, interval_seconds: float, clock: Callable[[], float]) -> None:
        self._interval = interval_seconds
        self._clock = clock
        self._links: dict[LinkKey, _LinkState] = {}

    def due(
        self, project_id: str, cf_project_id: str, snapshots: LinkSnapshots
    ) -> bool:
        """Whether the link is due now.

        True on first sight, once the interval has passed since the last complete
        read, or when the latest *observed* snapshot is new and records a change.
        A failed snapshot is never the latest observed row, so it triggers nothing;
        a recovery with no change is seen and triggers nothing. A trigger stays
        pending until a read completes, so a cut-off read stays due.
        """
        state = self._links.get((project_id, cf_project_id))
        if state is None:
            state = self._links[(project_id, cf_project_id)] = _LinkState()
        _note_snapshot(state, snapshots[1])
        if state.last_complete_at is None or state.trigger_pending:
            return True
        return self._clock() - state.last_complete_at >= self._interval

    def record_complete(self, project_id: str, cf_project_id: str) -> None:
        """A read finished and applied: restart the interval, clear any failure."""
        state = self._state(project_id, cf_project_id)
        state.last_complete_at = self._clock()
        state.trigger_pending = False
        state.last_failed = False

    def record_failed(self, project_id: str, cf_project_id: str) -> None:
        """A read failed. The link stays due, and counts as failing."""
        state = self._state(project_id, cf_project_id)
        state.trigger_pending = False
        state.last_failed = True

    def record_cut_off(self, project_id: str, cf_project_id: str) -> None:
        """The budget cut the read off: nothing changes, so the link stays due."""
        self._state(project_id, cf_project_id)

    def last_failed(self, project_id: str, cf_project_id: str) -> bool:
        """Whether the link's last read failed and none has succeeded since."""
        state = self._links.get((project_id, cf_project_id))
        return state is not None and state.last_failed

    def _state(self, project_id: str, cf_project_id: str) -> _LinkState:
        return self._links.setdefault((project_id, cf_project_id), _LinkState())


def _note_snapshot(state: _LinkState, observed: CFSnapshot | None) -> None:
    """Remember a new observed snapshot; a non-empty change makes the link due."""
    if observed is None or observed.id == state.seen_snapshot_id:
        return
    state.seen_snapshot_id = observed.id
    if observed.changed:
        state.trigger_pending = True
