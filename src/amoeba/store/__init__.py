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

from amoeba.store.attribution import Attribution, attribute_review
from amoeba.store.check_models import (
    CheckInput,
    CheckOutcome,
    CheckRecord,
    CheckStanding,
    ProgressInput,
    ProgressKind,
    check_standing,
)
from amoeba.store.evidence_models import (
    COMPARABLE_STANDINGS,
    FindingChange,
    FindingChanges,
    FindingInput,
    FindingObservation,
    FindingSeverity,
    FindingSummary,
    Provenance,
    RecordSource,
    ReviewVerdict,
    TaggedFinding,
    VerdictDerivation,
    VerdictInput,
    VerdictRecord,
    VerdictStanding,
    parse_severity,
    parse_verdict,
    verdict_standing,
)
from amoeba.store.feed_models import (
    BaselineEntry,
    Change,
    ChangeKind,
    DetectedReview,
    DetectionInput,
    DetectionOutcome,
    ReviewWatch,
)
from amoeba.store.inbox_models import (
    Channel,
    Message,
    QuarantineReason,
    SubmissionKind,
    SubmissionOutcome,
    SubmissionRecord,
)
from amoeba.store.journal_models import (
    REQUIRED_PARAMETER_KEYS,
    REVIEW_PRODUCING_KINDS,
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
    VerdictNotFoundError,
)
from amoeba.store.store import Store

__all__ = [
    # Vocabularies
    "BLOCKED_KIND_TO_STATUS",
    "BLOCKED_STATUSES",
    "REQUIRED_PARAMETER_KEYS",
    "REVIEW_PRODUCING_KINDS",
    "BlockedKind",
    "Channel",
    "CommandKind",
    "JournalOutcome",
    "JournalResolver",
    "NodeKind",
    "NodeStatus",
    "QuarantineReason",
    "SubmissionKind",
    "SubmissionOutcome",
    "COMPARABLE_STANDINGS",
    "FindingChange",
    "FindingSeverity",
    "CheckOutcome",
    "CheckStanding",
    "ProgressKind",
    "RecordSource",
    "ReviewVerdict",
    "VerdictDerivation",
    "VerdictStanding",
    "ChangeKind",
    "DetectionOutcome",
    # Evidence rules
    "parse_severity",
    "parse_verdict",
    "verdict_standing",
    "check_standing",
    "attribute_review",
    # Transfer objects
    "BlockedNode",
    "BlockedState",
    "CFReference",
    "JournalEntry",
    "Message",
    "Node",
    "Resolution",
    "SQReference",
    "SubmissionRecord",
    "FindingChanges",
    "FindingInput",
    "FindingObservation",
    "FindingSummary",
    "CheckInput",
    "CheckRecord",
    "ProgressInput",
    "Provenance",
    "TaggedFinding",
    "VerdictInput",
    "VerdictRecord",
    "Attribution",
    "BaselineEntry",
    "Change",
    "DetectedReview",
    "DetectionInput",
    "ReviewWatch",
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
    "VerdictNotFoundError",
]
