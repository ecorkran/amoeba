"""Desired-state reads, and the write ``acknowledge_message`` calls.

Mixed into ``Store``; see ``store.py`` for the assembled public class.

A desired state is written only inside an intent's acknowledgment (D3), so the
write here is internal and never commits: ``acknowledge_message`` calls it
inside its own transaction. What a desired state *means*, and how a node's path
resolves drive and hold, belongs to the Runner; this module stores what it is
given.
"""

from __future__ import annotations

from amoeba.store import sql_runner
from amoeba.store._base import StoreBase, new_id
from amoeba.store.inbox_models import Message
from amoeba.store.mapping_runner import map_desired_state
from amoeba.store.models import NodeNotFoundError
from amoeba.store.runner_models import (
    ClearDesiredState,
    DesiredState,
    SetDesiredState,
)


def _check_shape(change: SetDesiredState) -> None:
    """Apply D3's shape rules to a set. Each failure is a ``ValueError``."""
    if change.drive is None and change.hold is None:
        raise ValueError(
            "a desired state must set drive or hold; use ClearDesiredState to clear"
        )
    step = change.drive_until_step
    if step is not None:
        if change.drive is not True:
            raise ValueError("drive_until_step requires drive to be True")
        if not step.strip():
            raise ValueError("drive_until_step must be non-empty text")


class DesiredStateOperations(StoreBase):
    """Reads over ``desired_states`` and the in-transaction write."""

    def desired_state(
        self, project_id: str, *, node_id: str | None = None
    ) -> DesiredState | None:
        """The desired state at one target, or ``None`` when there is none.

        ``node_id=None`` is the project target. A row on an orphaned node is
        still returned; ignoring it is the Runner's rule.
        """
        if node_id is None:
            row = self._execute(
                sql_runner.SELECT_DESIRED_PROJECT_TARGET, (project_id,)
            ).fetchone()
        else:
            row = self._execute(
                sql_runner.SELECT_DESIRED_NODE_TARGET, (node_id,)
            ).fetchone()
        return None if row is None else map_desired_state(row)

    def desired_states(self, project_id: str) -> list[DesiredState]:
        """Every desired state in a project: the project target, then by node id."""
        rows = self._execute(
            sql_runner.SELECT_DESIRED_FOR_PROJECT, (project_id,)
        ).fetchall()
        return [map_desired_state(row) for row in rows]

    def _write_desired_state_change(
        self,
        intent: Message,
        change: SetDesiredState | ClearDesiredState,
        timestamp: str,
    ) -> None:
        """Apply a desired-state change on behalf of an acknowledged intent.

        Must be called **inside** the caller's transaction and never commits, so
        a failure rolls the acknowledgment back with it.

        Raises:
            ValueError: If a set breaks a shape rule.
            NodeNotFoundError: If the change names a node that is not in the
                intent's project.
        """
        if isinstance(change, SetDesiredState):
            _check_shape(change)
        self._require_node_in_project(change.node_id, intent.project_id)

        delete = (
            sql_runner.DELETE_DESIRED_PROJECT_TARGET
            if change.node_id is None
            else sql_runner.DELETE_DESIRED_NODE_TARGET
        )
        self._execute(
            delete, (intent.project_id if change.node_id is None else change.node_id,)
        )
        if isinstance(change, ClearDesiredState):
            return

        self._execute(
            sql_runner.INSERT_DESIRED_STATE,
            (
                new_id(),
                intent.project_id,
                change.node_id,
                None if change.drive is None else int(change.drive),
                change.drive_until_step,
                None if change.hold is None else int(change.hold),
                intent.id,
                timestamp,
            ),
        )

    def _require_node_in_project(self, node_id: str | None, project_id: str) -> None:
        if node_id is None:
            return
        node = self.get_node(node_id)
        if node is None or node.project_id != project_id:
            raise NodeNotFoundError(
                f"no node {node_id!r} in project {project_id!r} for a desired state"
            )
