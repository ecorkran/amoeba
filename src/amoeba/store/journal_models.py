"""Journal vocabularies and the journal entry transfer object.

Sibling of ``models.py`` rather than an extension of it: that module is already
at the ~200-line mark and the slice 101 convention is one definition site per
concern, not one growing file.

Every journal string lives here. No outcome, kind, or resolver literal appears
anywhere else in the package — the statements in ``sql_journal.py`` reference
these members, and so does every call site. This module knows nothing about SQL
or ``sqlite3``.

The vocabularies are closed. A stored value outside one is an error on read, not
a default, exactly as in ``models.py``: "unknown is a value, not a default" at
the storage boundary. Note that :attr:`JournalOutcome.UNKNOWN` is a *recorded
outcome* — recovery could not determine what happened — and is not the same
thing as an unmappable stored string.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Final


class CommandKind(StrEnum):
    """The side-effecting commands the journal records.

    Adding a member is a three-part change: the member, its entry in
    :data:`REQUIRED_PARAMETER_KEYS`, and an observer registered for it in
    recovery. A kind with no observer escalates rather than being skipped.
    """

    CF_WRITE = "cf_write"
    SQ_RUN = "sq_run"


class JournalOutcome(StrEnum):
    """How a journal entry was closed.

    ``COMPLETED`` and ``FAILED`` are written by the issuer, which observed the
    command itself. The remaining three are written only by recovery, which did
    not — it reconstructed the outcome by observing the external system.
    """

    COMPLETED = "completed"
    FAILED = "failed"
    ADOPTED = "adopted"
    NOT_APPLIED = "not_applied"
    UNKNOWN = "unknown"


class JournalResolver(StrEnum):
    """Who closed an entry — the issuer that ran it, or recovery."""

    ISSUER = "issuer"
    RECOVERY = "recovery"


#: The parameter key that carries an ``sq_run``'s Squadron run id (slice 120).
PARAM_RUN_ID: Final = "run_id"

#: Optional ``sq_run`` keys that mark a continuation of an earlier run (slice 127):
#: what it does (``retry``, ``accept`` or ``observe``), the entry it continues, and
#: the resolution it carries out. ``PARAM_RESOLUTION`` is also optional on a
#: ``cf_write``, naming the resolution a rerun's pointer write carries out. The
#: recovery observer checks only that ``PARAM_CONTINUATION`` is present.
PARAM_CONTINUATION: Final = "continuation"
PARAM_CONTINUES: Final = "continues"
PARAM_RESOLUTION: Final = "resolution"

#: The parameter key that carries the working directory a command runs in (slice 122
#: for ``sq_run``, slice 125 for ``cf_write``): the absolute path of the checkout.
#: Stored and returned unchanged. An ``sq_run`` does not require it; a ``cf_write``
#: does, because its read-back must run ``cf`` in the same checkout.
PARAM_CHECKOUT: Final = "checkout"

#: The optional ``cf_write`` parameter key naming the slice index the write sets
#: (slice 125). The read-back compares it with the index parsed from ``fileSlice``.
PARAM_EXPECTED_SLICE_INDEX: Final = "expected_slice_index"

#: The ``cf_write`` parameter keys naming the CF project id and the expected record
#: (both required at issue time).
PARAM_PROJECT: Final = "project"
PARAM_EXPECTED: Final = "expected"

#: The parameter keys each command kind must carry at issue time.
#:
#: Validated by ``journal_issue`` *before* anything is written, because the
#: failure this prevents is discovering after a crash that an entry cannot be
#: reconciled — its matching fields were never recorded. Declared as one mapping
#: rather than as conditionals at the call site, so a new kind cannot be added
#: without declaring what recovery needs from it.
#:
#: Additional keys beyond these are stored and returned unchanged.
REQUIRED_PARAMETER_KEYS: Final[Mapping[CommandKind, frozenset[str]]] = {
    CommandKind.CF_WRITE: frozenset({PARAM_PROJECT, PARAM_EXPECTED, PARAM_CHECKOUT}),
    CommandKind.SQ_RUN: frozenset({"pipeline", "params", PARAM_RUN_ID}),
}


#: The command kinds whose side effect is a review file (D5 of slice 106).
#: While a project has an unresolved entry of one of these kinds, review
#: detection does not scan it: the Runner owns that review. Initiative 120
#: adds its review command kind here.
REVIEW_PRODUCING_KINDS: Final[frozenset[CommandKind]] = frozenset({CommandKind.SQ_RUN})


@dataclass(frozen=True)
class JournalEntry:
    """One journaled command: what was issued, and how it was closed.

    An entry is written and committed *before* the side effect is issued, and
    closed when its result arrives. An entry with ``outcome`` still ``None`` is
    therefore exactly the thing recovery reconciles: a command that may or may
    not have reached the external system.

    ``parameters`` and ``result`` are stored verbatim and are shown by
    ``amoeba inspect``. Callers must not place secrets in them.
    """

    id: str
    project_id: str
    node_id: str
    kind: CommandKind
    parameters: Mapping[str, object] = field(default_factory=dict[str, object])
    issued_at: datetime | None = None
    outcome: JournalOutcome | None = None
    result: Mapping[str, object] | None = None
    resolved_at: datetime | None = None
    resolved_by: JournalResolver | None = None
    #: Set when a Runner resolution left evidence awaiting a routing decision
    #: (slice 125, D8). Never set by recovery, and cleared by a decision.
    awaits_routing: bool = False

    @property
    def is_resolved(self) -> bool:
        """Whether the entry has been closed.

        Derived from ``outcome`` rather than stored beside it, so the two can
        never disagree.
        """
        return self.outcome is not None


def latest_run_entry(entries: Sequence[JournalEntry]) -> JournalEntry | None:
    """The newest ``sq_run`` entry of ``entries`` (oldest first), or ``None``."""
    return next((e for e in reversed(entries) if e.kind is CommandKind.SQ_RUN), None)
