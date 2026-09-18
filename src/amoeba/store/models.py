"""Closed vocabularies, transfer objects, and the store exception hierarchy.

This module fixes the vocabulary every other module in the package references.
It knows nothing about SQL or ``sqlite3``: the mapping between these types and
database rows lives in one place, in ``store.py``.

A value read back that is not in one of these vocabularies is an error, not a
default — "unknown is a value, not a default" at the storage boundary.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class NodeStatus(StrEnum):
    """Lifecycle status of a node. The closed status vocabulary.

    ``StrEnum`` so the stored values are readable strings when the database file
    is inspected directly — the slice 102 inspection surface reads them.
    """

    RUNNABLE = "runnable"
    IN_PROGRESS = "in_progress"
    BLOCKED_ON_HUMAN = "blocked_on_human"
    BLOCKED_ON_JUDGE = "blocked_on_judge"
    BLOCKED_ON_SQ_CHECKPOINT = "blocked_on_sq_checkpoint"
    DONE = "done"


#: The statuses that mean a node is waiting on something outside the Runner.
#: Defined once here so the blocked query and the transition checks agree by
#: construction rather than by two lists staying in sync.
BLOCKED_STATUSES: frozenset[NodeStatus] = frozenset(
    {
        NodeStatus.BLOCKED_ON_HUMAN,
        NodeStatus.BLOCKED_ON_JUDGE,
        NodeStatus.BLOCKED_ON_SQ_CHECKPOINT,
    }
)


class NodeKind(StrEnum):
    """What a node represents in the lifecycle tree."""

    INITIATIVE = "initiative"
    PHASE_OR_ARTIFACT = "phase_or_artifact"
    SLICE = "slice"
    GATE = "gate"


class BlockedKind(StrEnum):
    """What a blocked node is waiting on.

    Parallel to the ``blocked_on_*`` statuses but a separate vocabulary: the
    status says the node is blocked, this says on whom.
    """

    HUMAN = "human"
    JUDGE = "judge"
    SQ_CHECKPOINT = "sq_checkpoint"


#: The blocked status each blocker kind puts its node into. Defined once so
#: ``block()`` never has to choose, and status and blocked-state cannot drift.
BLOCKED_KIND_TO_STATUS: dict[BlockedKind, NodeStatus] = {
    BlockedKind.HUMAN: NodeStatus.BLOCKED_ON_HUMAN,
    BlockedKind.JUDGE: NodeStatus.BLOCKED_ON_JUDGE,
    BlockedKind.SQ_CHECKPOINT: NodeStatus.BLOCKED_ON_SQ_CHECKPOINT,
}


@dataclass(frozen=True)
class CFReference:
    """Context Forge coordinates for a node.

    Held as opaque values. The store never parses these; slice 104 correlates
    provenance against them and the Runner, not the store, parses CF output.
    """

    project: str | None = None
    phase: str | None = None
    slice_name: str | None = None
    artifact_path: str | None = None


@dataclass(frozen=True)
class SQReference:
    """Squadron coordinates for a node.

    Held as opaque values, exactly as CF references are. Squadron run ids have
    the form ``run-{date}-{slug}-{uuid8}``, but the store treats them as
    strings and never decomposes them.
    """

    run_id: str | None = None
    review_artifact_path: str | None = None
    reviewed_sha: str | None = None


@dataclass(frozen=True)
class Node:
    """A node in the project-keyed lifecycle tree."""

    id: str
    project_id: str
    kind: NodeKind
    status: NodeStatus
    title: str
    parent_id: str | None = None
    cf: CFReference = field(default_factory=CFReference)
    sq: SQReference = field(default_factory=SQReference)
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True)
class Resolution:
    """What filled a blocked state's resolution slot, and who supplied it."""

    resolved_by: str
    detail: str
    resolved_at: datetime | None = None


@dataclass(frozen=True)
class BlockedState:
    """A node's blocked state, with an explicit — possibly unfilled — slot.

    The resolution slot being nullable is the schema-level expression of
    checkpoint-as-persisted-blocked-state: an unfilled slot *is* the checkpoint.
    """

    id: str
    node_id: str
    kind: BlockedKind
    context: str
    resolution: Resolution | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @property
    def is_resolved(self) -> bool:
        """Whether the resolution slot has been filled."""
        return self.resolution is not None


@dataclass(frozen=True)
class BlockedNode:
    """A blocked node together with its blocked state.

    The blocked query returns these so "on whom" is answered without a second
    call, per the API contract.
    """

    node: Node
    blocked_state: BlockedState


class StoreError(Exception):
    """Base class for every error this package raises."""


class StoreSchemaError(StoreError):
    """The store's schema version cannot be reconciled with this code."""


class StoreCorruptError(StoreError):
    """The store file is not a readable SQLite database."""


class StorePermissionError(StoreError):
    """The store path cannot be read, written, or created."""


class StoreBusyError(StoreError):
    """The busy timeout was exhausted waiting for a lock."""


class StoreIntegrityError(StoreError):
    """A write would violate the store's own invariants."""


class NodeNotFoundError(StoreError):
    """No node exists with the given id."""


class InvalidTransitionError(StoreError):
    """A block or resolve was attempted against a node in the wrong state."""


class UnknownVocabularyValueError(StoreError):
    """A stored value is outside its closed vocabulary.

    Raised on read rather than substituting a default, so a corrupted or
    hand-edited row surfaces instead of silently becoming a valid-looking
    object.
    """
