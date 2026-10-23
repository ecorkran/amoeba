"""Closed vocabularies and transfer objects for the Runner's store contract.

Routing decisions, routing-table versions and desired states (slice 121). Like
``models.py``, this module knows nothing about SQL or ``sqlite3``. What a route
or a desired state *means* belongs to the Runner slices; the store only holds
them.

``Route`` is the one definition 126 imports. ``inputs``, ``route_parameters``,
table ``content`` and escalation payloads are stored verbatim and shown by
inspection, so callers must not place secrets in them.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from amoeba.store.models import NodeStatus


class Route(StrEnum):
    """Where a routing decision sends a node."""

    ADVANCE = "advance"
    RERUN = "rerun"
    ESCALATE = "escalate"


@dataclass(frozen=True)
class RoutingTableVersion:
    """One version of a routing table.

    Write-once: a version, once stored, keeps its content. ``first_used_at`` is
    ``None`` on a value a caller passes in and set on one read back.
    """

    version: str
    content: str
    first_used_at: datetime | None = None


@dataclass(frozen=True)
class RoutingDecisionInput:
    """What a caller supplies to record a routing decision.

    ``inputs`` and ``route_parameters`` are JSON objects. The text fields must
    be non-empty. ``journal_entry_id`` is the outcome entry being routed, if any.
    """

    project_id: str
    node_id: str
    inputs: Mapping[str, object]
    rule_id: str
    table_version: str
    amoeba_version: str
    route: Route
    route_parameters: Mapping[str, object]
    journal_entry_id: str | None = None


@dataclass(frozen=True)
class RoutingDecision:
    """A stored routing decision.

    ``attempt_count`` is the counter's value after this decision's increment,
    or ``None`` when the decision did not count an attempt.
    """

    id: str
    project_id: str
    node_id: str
    inputs: Mapping[str, object]
    rule_id: str
    table_version: str
    amoeba_version: str
    route: Route
    route_parameters: Mapping[str, object]
    decided_at: datetime
    journal_entry_id: str | None = None
    attempt_step: str | None = None
    attempt_count: int | None = None


@dataclass(frozen=True)
class StatusEffect:
    """A decision's effect: move the node to a status."""

    status: NodeStatus


@dataclass(frozen=True)
class BlockEffect:
    """A decision's effect: block the node on a human, with an escalation."""

    context: str
    payload: Mapping[str, object] | None = None


@dataclass(frozen=True)
class SetDesiredState:
    """Replace a target's whole desired-state row.

    ``node_id=None`` is the project target. ``drive`` and ``hold`` are nullable
    booleans: ``None`` means not set at this target.
    """

    node_id: str | None = None
    drive: bool | None = None
    drive_until_step: str | None = None
    hold: bool | None = None


@dataclass(frozen=True)
class ClearDesiredState:
    """Delete a target's desired-state row. ``node_id=None`` is the project."""

    node_id: str | None = None


@dataclass(frozen=True)
class DesiredState:
    """A stored desired state. ``message_id`` is the intent that last set it."""

    id: str
    project_id: str
    message_id: str
    updated_at: datetime
    node_id: str | None = None
    drive: bool | None = None
    drive_until_step: str | None = None
    hold: bool | None = None
