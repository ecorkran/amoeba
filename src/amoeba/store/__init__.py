"""The Amoeba lifecycle node store — the contract downstream slices code against.

This package holds a project-keyed tree of lifecycle nodes in one SQLite file: a
closed status vocabulary, blocked states with an explicit resolution slot, and
the two queries the Runner's loop consumes. A blocked node with an unfilled
resolution slot *is* a checkpoint — that is the decision this schema exists to
express.

The full contract is documented in ``docs/store-contract.md``, which is written
to be sufficient for designing a consumer without reading this implementation.

Exported here is the contract and only the contract: SQL statements, column
constants, row mapping, path resolution, and migration machinery are internal
and deliberately not re-exported.
"""

from __future__ import annotations

from amoeba.store.journal_models import (
    REQUIRED_PARAMETER_KEYS,
    CommandKind,
    JournalEntry,
    JournalOutcome,
    JournalResolver,
)
from amoeba.store.models import (
    BLOCKED_KIND_TO_STATUS,
    BLOCKED_STATUSES,
    BlockedKind,
    BlockedNode,
    BlockedState,
    CFReference,
    InvalidTransitionError,
    Node,
    NodeKind,
    NodeNotFoundError,
    NodeStatus,
    Resolution,
    SQReference,
    StoreBusyError,
    StoreCorruptError,
    StoreError,
    StoreIntegrityError,
    StorePermissionError,
    StoreSchemaError,
    UnknownVocabularyValueError,
)
from amoeba.store.store import Store

__all__ = [
    # Vocabularies
    "BLOCKED_KIND_TO_STATUS",
    "BLOCKED_STATUSES",
    "REQUIRED_PARAMETER_KEYS",
    "BlockedKind",
    "CommandKind",
    "JournalOutcome",
    "JournalResolver",
    "NodeKind",
    "NodeStatus",
    # Transfer objects
    "BlockedNode",
    "BlockedState",
    "CFReference",
    "JournalEntry",
    "Node",
    "Resolution",
    "SQReference",
    # The store
    "Store",
    # Exceptions
    "InvalidTransitionError",
    "NodeNotFoundError",
    "StoreBusyError",
    "StoreCorruptError",
    "StoreError",
    "StoreIntegrityError",
    "StorePermissionError",
    "StoreSchemaError",
    "UnknownVocabularyValueError",
]
