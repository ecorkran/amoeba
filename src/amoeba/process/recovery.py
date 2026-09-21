"""The reconcile-by-observation recovery protocol.

On start, every journaled-but-unresolved entry is reconciled by **observing the
external system** — never by re-issuing the command. An entry that cannot be
resolved to exactly one observed effect becomes an explicit ``blocked_on_human``
node carrying the journal entry, because a wrong adoption is silent and a human
interruption is not.

This module knows nothing about Squadron or Context Forge. It is written against
the :class:`Observer` protocol; the modules under ``observers/`` are what know
about a specific upstream. That separation is the point: adding a command kind
means adding an enum member, its required parameter keys, and an observer, with
no change here.

Each entry is reconciled in its **own transaction**, so recovery is itself
crash-safe: a second crash partway through re-runs only what is still
unresolved.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Protocol

from amoeba.store import Store
from amoeba.store.journal_models import (
    CommandKind,
    JournalEntry,
    JournalOutcome,
    JournalResolver,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Adopt:
    """The command reached the external system; adopt the observed effect.

    ``result`` carries what to record on the entry — for Squadron the matched
    ``run_id`` and the run file's own ``schema_version`` as provenance; for
    Context Forge the project record's ``updatedAt`` and a captured version
    label.
    """

    result: Mapping[str, object]


@dataclass(frozen=True)
class NotApplied:
    """The command demonstrably did not reach the external system.

    Only an observer that can distinguish "did not happen" from "cannot tell"
    returns this. Squadron cannot — a pruned run and a never-issued run present
    identically — so it returns :class:`Unknown` instead.
    """

    reason: str


@dataclass(frozen=True)
class Unknown:
    """The observation was ambiguous; a human must decide.

    Every ambiguity lands here: no observer registered for the kind, zero
    candidates, several candidates, an unreadable upstream, a parse failure, a
    missing required field. ``candidates`` carries whatever was seen, so the
    human reading the blocked state has something to work from.
    """

    reason: str
    candidates: tuple[str, ...] = field(default_factory=tuple)


#: The three possible observations. Exhaustive under ``pyright`` strict: a
#: ``match`` over this union needs no fallback case, which is what makes adding
#: a fourth kind of answer a type error rather than a silent fall-through.
type Observation = Adopt | NotApplied | Unknown


class Observer(Protocol):
    """Answers what the external system shows for one journaled command.

    An observer **never** issues, retries, or repairs anything. It looks, and
    it reports. Expected external failure — a missing directory, a timeout, an
    unparseable file — is reported as :class:`Unknown`, not raised: those are
    answers, not bugs. An unexpected exception propagates and aborts startup.
    """

    def observe(self, entry: JournalEntry) -> Observation:
        """Report what the external system shows for ``entry``."""
        ...


#: Observers by the command kind they can answer for. A kind absent from the
#: registry is treated as :class:`Unknown` — escalated, never skipped.
type ObserverRegistry = Mapping[CommandKind, Observer]


@dataclass(frozen=True)
class RecoverySummary:
    """Counts by outcome, for the startup log line."""

    adopted: int = 0
    not_applied: int = 0
    unknown: int = 0

    @property
    def total(self) -> int:
        """How many entries were reconciled."""
        return self.adopted + self.not_applied + self.unknown

    def describe(self) -> str:
        """Render the summary the way the startup log states it."""
        if self.total == 0:
            return "nothing to reconcile"
        return (
            f"{self.adopted} adopted, "
            f"{self.not_applied} not_applied, "
            f"{self.unknown} unknown"
        )


def reconcile(
    store: Store, project_id: str, registry: ObserverRegistry
) -> RecoverySummary:
    """Reconcile every unresolved entry for a project, oldest first.

    Each entry is resolved in its own transaction — the store methods each
    commit — so an interrupted recovery re-runs only what is still unresolved
    and never reconciles an entry twice.

    Args:
        store: A read-write store for the project.
        project_id: The project whose journal to reconcile.
        registry: Observers by command kind. A kind with no observer escalates.

    Returns:
        Counts by outcome.

    Raises:
        Exception: Whatever an observer or the store raised unexpectedly. It is
            logged and re-raised rather than swallowed: recovery that cannot
            complete aborts startup rather than letting tenants run against
            unreconciled state.
    """
    adopted = 0
    not_applied = 0
    unknown = 0

    for entry in store.unresolved_journal_entries(project_id):
        observation = _observe(entry, registry)

        match observation:
            case Adopt(result=result):
                store.journal_resolve(
                    entry.id,
                    outcome=JournalOutcome.ADOPTED,
                    result=result,
                    resolved_by=JournalResolver.RECOVERY,
                )
                adopted += 1
            case NotApplied(reason=reason):
                store.journal_resolve(
                    entry.id,
                    outcome=JournalOutcome.NOT_APPLIED,
                    result={"reason": reason},
                    resolved_by=JournalResolver.RECOVERY,
                )
                not_applied += 1
            case Unknown(reason=reason, candidates=candidates):
                store.journal_escalate(
                    entry.id, reason=_escalation_reason(reason, candidates)
                )
                unknown += 1

    return RecoverySummary(adopted=adopted, not_applied=not_applied, unknown=unknown)


def _observe(entry: JournalEntry, registry: ObserverRegistry) -> Observation:
    """Dispatch one entry to its observer.

    A missing observer is :class:`Unknown`, not an error and not a skip: the
    command may well have reached the external system, and nothing here can
    tell. Escalating is the honest answer.
    """
    observer = registry.get(entry.kind)
    if observer is None:
        return Unknown(reason=f"no observer registered for kind {entry.kind.value!r}")

    try:
        return observer.observe(entry)
    except Exception:
        # Re-raised after logging, per the project exception rule: an observer
        # raising is a bug in the observer, and recovery that cannot complete
        # must abort startup rather than guess at this entry.
        logger.exception(
            "observer for %s raised on journal entry %s", entry.kind.value, entry.id
        )
        raise


def _escalation_reason(reason: str, candidates: tuple[str, ...]) -> str:
    """Compose the blocked-state reason, naming candidates when there are any."""
    if not candidates:
        return reason
    return f"{reason} (candidates: {', '.join(candidates)})"
