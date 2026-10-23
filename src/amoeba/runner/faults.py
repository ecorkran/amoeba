"""The fault vocabulary the Runner's modules share.

Defined once so the observe, act and tenant modules import the same values.
Escalation writes join this module in a later task.

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
    Store,
    StoreBusyError,
    StoreCorruptError,
    StorePermissionError,
    StoreSchemaError,
)


class FaultKind(StrEnum):
    """Why the Runner raised an escalation or blocked a node."""

    RUN_OBSERVATION_FAILED = "run_observation_failed"
    LAUNCH_OVERDUE = "launch_overdue"
    CF_PROBE_FAILED = "cf_probe_failed"
    UNEXPECTED_FAULT = "unexpected_fault"


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
