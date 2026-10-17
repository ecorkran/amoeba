"""Context Forge links and snapshots: the ``link_cf_project`` effect, and reads
and in-process writes of the snapshot log.

Mixed into ``Store``; see ``store.py`` for the assembled public class.

Changes are never written here: migration ``008``'s trigger emits one per
snapshot inside the transaction of the insert (108, D6). The store reads no
file and asks nothing of Context Forge: ``observed_at`` comes from the caller,
and whether a linked id exists is answered by the watch's first check.
"""

from __future__ import annotations

from amoeba.store import sql_cf, sql_inbox
from amoeba.store._base import StoreBase
from amoeba.store.cf_models import (
    CFLink,
    CFSnapshot,
    CFSnapshotInput,
    CFSnapshotOutcome,
)
from amoeba.store.mapping_cf import map_link, map_snapshot, snapshot_parameters
from amoeba.store.models import StoreIntegrityError


def _check_shape(snapshot: CFSnapshotInput) -> None:
    """An ``observed`` row carries a state and changes and no detail; a failure
    carries a detail and neither. A caller that mixes them has a bug, and the
    feed payload would misreport it."""
    observed = snapshot.outcome is CFSnapshotOutcome.OBSERVED
    if observed != (snapshot.state is not None) or observed != (
        snapshot.changed is not None
    ):
        raise ValueError(
            f"a {snapshot.outcome.value!r} snapshot "
            f"{'needs' if observed else 'must not have'} a state and changes"
        )
    if observed == (snapshot.detail is not None):
        raise ValueError(
            f"a {snapshot.outcome.value!r} snapshot "
            f"{'must not have' if observed else 'needs'} a detail"
        )


class CFWriter(StoreBase):
    """The inbox's ``link_cf_project`` effect. Never commits."""

    def _link_cf_project(
        self, project_id: str, cf_project_id: str, linked_at: str
    ) -> None:
        """Link, inside ``apply_submission``'s transaction. Linking again is a no-op."""
        self._execute(sql_cf.INSERT_LINK, (project_id, cf_project_id, linked_at))


class CFOperations(CFWriter):
    """Reads of links and snapshots, and the snapshot write path."""

    def cf_links(self, project_id: str) -> list[CFLink]:
        """A project's links, in the order they were linked."""
        rows = self._execute(sql_cf.SELECT_LINKS, (project_id,)).fetchall()
        return [map_link(row) for row in rows]

    def cf_snapshots(self, project_id: str) -> list[CFSnapshot]:
        """A project's snapshots, in id order."""
        rows = self._execute(sql_cf.SELECT_SNAPSHOTS, (project_id,)).fetchall()
        return [map_snapshot(row) for row in rows]

    def latest_cf_snapshots(
        self, project_id: str, cf_project_id: str
    ) -> tuple[CFSnapshot | None, CFSnapshot | None]:
        """The link's latest snapshot, and its latest ``observed`` one.

        Either is ``None`` when there is none; they are the same row when the
        latest snapshot is itself ``observed``.
        """
        latest = self._execute(
            sql_cf.SELECT_LATEST_SNAPSHOT, (project_id, cf_project_id)
        ).fetchone()
        observed = self._execute(
            sql_cf.SELECT_LATEST_OBSERVED_SNAPSHOT,
            (project_id, cf_project_id, CFSnapshotOutcome.OBSERVED.value),
        ).fetchone()
        return (
            None if latest is None else map_snapshot(latest),
            None if observed is None else map_snapshot(observed),
        )

    def record_cf_snapshot(self, snapshot: CFSnapshotInput) -> CFSnapshot:
        """Record one snapshot. In-process only: one insert, and its trigger.

        Raises:
            ValueError: If the outcome and the state, changes, and detail
                disagree (see :class:`CFSnapshotInput`). Nothing is written.
        """
        _check_shape(snapshot)
        with self._connection:
            self._execute(sql_inbox.BEGIN_IMMEDIATE, ())
            cursor = self._execute(
                sql_cf.INSERT_SNAPSHOT, snapshot_parameters(snapshot)
            )
            row = self._execute(
                sql_cf.SELECT_SNAPSHOT_BY_ID, (cursor.lastrowid,)
            ).fetchone()
        if row is None:
            raise StoreIntegrityError(
                f"snapshot {cursor.lastrowid!r} vanished after insert"
            )
        return map_snapshot(row)
