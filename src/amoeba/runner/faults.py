"""The fault vocabulary the Runner's modules share.

Defined once so the observe, act and tenant modules import the same values,
along with the escalation writes for expected and unexpected faults.

An *expected* fault (a poll that gave no usable answer, an overdue launch) is an
answer, not an exception: a stage adds it to the tick's :class:`TickFaults` and
carries on.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from amoeba.store import (
    PARAM_RUN_ID,
    BlockedKind,
    CommandKind,
    NodeStatus,
    Store,
    StoreBusyError,
    StoreCorruptError,
    StorePermissionError,
    StoreSchemaError,
)


class FaultKind(StrEnum):
    """Why the Runner raised an escalation or blocked a node.

    ``PLAN_READ_FAILED`` is project-scoped only: a CF plan read that failed, or one
    that broke a reconcile safety rule. ``LIFECYCLE_ORPHAN`` and
    ``PLAN_STATUS_UNKNOWN`` are node-scoped: they name the ``fault_kind`` payload
    of a block on the node CF stopped reporting, or whose status the Runner cannot
    project. They are closed by resolving the block, not by the project rule.
    """

    RUN_OBSERVATION_FAILED = "run_observation_failed"
    LAUNCH_OVERDUE = "launch_overdue"
    CF_PROBE_FAILED = "cf_probe_failed"
    UNEXPECTED_FAULT = "unexpected_fault"
    PLAN_READ_FAILED = "plan_read_failed"
    LIFECYCLE_ORPHAN = "lifecycle_orphan"
    PLAN_STATUS_UNKNOWN = "plan_status_unknown"


class LaunchFailure(StrEnum):
    """How a detached launch failed before its run was confirmed."""

    SPAWN_ERROR = "spawn_error"
    EXITED_BEFORE_LINE = "exited_before_line"
    USAGE_ERROR = "usage_error"


#: A failure of the store itself. These are never a per-project fault: the
#: Runner re-raises them so the process stops rather than running blind.
STORE_FAILURES: Final = (
    StoreBusyError,
    StoreCorruptError,
    StorePermissionError,
    StoreSchemaError,
    sqlite3.Error,
)


@dataclass(frozen=True)
class Fault:
    """One expected fault a tick met.

    ``node_id`` and ``run_id`` name what it concerns, when known; ``detail`` is
    the text an operator reads.
    """

    kind: FaultKind
    detail: str
    node_id: str | None = None
    run_id: str | None = None


class TickFaults:
    """The expected faults one project tick has met so far."""

    def __init__(self) -> None:
        self._faults: list[Fault] = []

    def add(self, fault: Fault) -> None:
        """Record a fault."""
        self._faults.append(fault)

    def kinds(self) -> frozenset[FaultKind]:
        """The distinct kinds met; closure keeps open any kind in this set."""
        return frozenset(fault.kind for fault in self._faults)

    def __iter__(self) -> Iterator[Fault]:
        return iter(self._faults)

    def __len__(self) -> int:
        return len(self._faults)


class NodeContext:
    """The node a tick is working on, so the process-boundary catch can name it.

    Each node-scoped step sets it before it runs, as the host does for the
    current tenant. ``None`` means no node is in context.
    """

    def __init__(self) -> None:
        self.node_id: str | None = None

    def set(self, node_id: str) -> None:
        """Name the node the next step concerns."""
        self.node_id = node_id

    def clear(self) -> None:
        """Leave no node in context."""
        self.node_id = None


#: Keys of a project-scoped escalation's payload.
PAYLOAD_DETAIL: Final = "detail"
PAYLOAD_NODE_ID: Final = "node_id"
PAYLOAD_RUN_ID: Final = "run_id"


def raise_expected_faults(store: Store, project_id: str, faults: TickFaults) -> bool:
    """Raise each expected fault as a project-scoped escalation.

    Deduplicated by the store on ``(project, kind)``: a kind already open
    writes nothing, so a fault that recurs every tick adds no rows.

    Returns:
        Whether any escalation row was written.
    """
    already_open = {m.fault_kind for m in store.open_project_escalations(project_id)}
    wrote = False
    for fault in faults:
        store.raise_project_escalation(
            project_id,
            fault_kind=fault.kind.value,
            payload={
                PAYLOAD_DETAIL: fault.detail,
                PAYLOAD_NODE_ID: fault.node_id,
                PAYLOAD_RUN_ID: fault.run_id,
            },
        )
        wrote = wrote or fault.kind.value not in already_open
        already_open.add(fault.kind.value)
    return wrote


#: Keys of a node block's payload for an unexpected fault.
PAYLOAD_FAULT_KIND: Final = "fault_kind"
PAYLOAD_ERROR: Final = "error"
PAYLOAD_RUN_IDS: Final = "run_ids"

#: Keys of a lifecycle block's payload (orphan, unknown status, human step).
PAYLOAD_CF_PROJECT_ID: Final = "cf_project_id"
PAYLOAD_INDEX: Final = "index"
PAYLOAD_FORMER_INDEX: Final = "former_index"
PAYLOAD_FORMER_SLICE_NAME: Final = "former_slice_name"
PAYLOAD_STATUS: Final = "status"
PAYLOAD_STEP: Final = "step"


def escalate(
    store: Store,
    project_id: str,
    context: NodeContext,
    fault_kind: FaultKind,
    error: BaseException,
) -> None:
    """Escalate an unexpected fault: block the node in context, else the project.

    A node with no run in flight, not done and not already blocked is blocked on
    a human, with the fault named in the context and payload. A node already
    blocked on a human gets nothing more, so a fault repeating cannot storm; one
    blocked on anything else (a checkpoint, the judge) is not waiting on a human,
    so the fault takes the project-scoped path. A node with a
    run in flight (it blocks only when its run ends, D2), a done node (121, D1:
    it cannot be blocked) and no node at all take the project-scoped path, which
    the store deduplicates on ``(project, kind)``.
    """
    node_id = context.node_id
    node = None if node_id is None else store.get_node(node_id)
    run_ids = [] if node is None else _in_flight_run_ids(store, project_id, node.id)
    if node is not None and not run_ids and node.status is not NodeStatus.DONE:
        existing = store.blocked_state_for(node.id)
        if existing is None:
            store.block(
                node.id,
                kind=BlockedKind.HUMAN,
                context=f"{fault_kind.value}: {error}",
                payload={
                    PAYLOAD_FAULT_KIND: fault_kind.value,
                    PAYLOAD_ERROR: str(error),
                },
            )
            return
        if existing.kind is BlockedKind.HUMAN:
            return
    store.raise_project_escalation(
        project_id,
        fault_kind=fault_kind.value,
        payload={
            PAYLOAD_DETAIL: str(error),
            PAYLOAD_NODE_ID: node_id,
            PAYLOAD_RUN_IDS: run_ids,
        },
    )


def _in_flight_run_ids(store: Store, project_id: str, node_id: str) -> list[str]:
    # A legacy entry (journaled before slice 120) carries no run id: it is still
    # a run in flight for this node, so it is named by its entry id instead.
    return [
        str(entry.parameters.get(PARAM_RUN_ID, entry.id))
        for entry in store.unresolved_journal_entries(project_id)
        if entry.node_id == node_id and entry.kind is CommandKind.SQ_RUN
    ]
