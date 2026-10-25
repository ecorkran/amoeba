"""Gather what the store holds about one ingested outcome (D5).

Store reads only; nothing is written. The result is :class:`OutcomeEvidence`, which
``reduce`` turns into routing inputs. Ingestion (125) resolved the entry and left
its result; the journal entry, the node and the recorded verdicts are all read
back here.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import cast

from amoeba.process import RunOutcomeDocument
from amoeba.runner.finish import RESULT_LAUNCH_FAILURE, RESULT_RESUME_FAILURE
from amoeba.runner.ingest.record import (
    RESULT_OUTCOME,
    RESULT_OUTCOME_DOCUMENT,
    RESULT_REVIEW_FAULT,
    RESULT_VERDICT_IDS,
)
from amoeba.runner.lifecycle.steps import LifecycleStep
from amoeba.runner.routing.inputs import ROUTED_SEVERITIES, SEVERITY_LOW_TO_HIGH
from amoeba.runner.routing.reduce import OutcomeEvidence, ReviewPart
from amoeba.store import (
    PARAM_CONTINUATION,
    PARAM_CONTINUES,
    FindingSeverity,
    JournalEntry,
    Store,
    VerdictNotFoundError,
)


def gather(store: Store, entry: JournalEntry) -> OutcomeEvidence:
    """Read ``entry``'s result, its node and its recorded reviews."""
    result = entry.result
    if result is None:
        raise ValueError(f"entry {entry.id} is awaiting routing with no result")
    node = store.get_node(entry.node_id)
    if node is None:
        raise ValueError(f"entry {entry.id} names a node that is gone: {entry.node_id}")
    step = node.cf.phase
    outcome = result.get(RESULT_OUTCOME)
    document = result.get(RESULT_OUTCOME_DOCUMENT)
    parsed = (
        RunOutcomeDocument.model_validate(document)
        if isinstance(document, dict)
        else None
    )
    verdict_ids = _verdict_ids(result.get(RESULT_VERDICT_IDS))
    parts = _read_parts(store, verdict_ids)
    continuation = entry.parameters.get(PARAM_CONTINUATION)
    return OutcomeEvidence(
        outcome=outcome if isinstance(outcome, str) else None,
        launch_failed=RESULT_LAUNCH_FAILURE in result,
        resume_failed=RESULT_RESUME_FAILURE in result,
        continuation=continuation if isinstance(continuation, str) else None,
        verdict_ids=tuple(verdict_ids),
        continued_verdict_ids=_continued_verdict_ids(store, entry),
        checkpoint=None if parsed is None else parsed.checkpoint,
        failure=None if parsed is None else parsed.failure,
        step=step,
        node_status=node.status,
        attempt_count=_attempts(store, node.id, step),
        review_fault=result.get(RESULT_REVIEW_FAULT) is not None,
        review_unreadable=parts is None,
        parts=parts or (),
    )


def _continued_verdict_ids(store: Store, entry: JournalEntry) -> tuple[str, ...] | None:
    """The reviews recorded on the entry this one continues, one store read.

    ``None`` for an ordinary run, and when the continued entry or its ids cannot be
    read; ``reduce`` turns the latter into ``unknown`` for an accept.
    """
    continues = entry.parameters.get(PARAM_CONTINUES)
    if not isinstance(continues, str):
        return None
    continued = store.journal_entry(continues)
    if continued is None or continued.result is None:
        return None
    try:
        return tuple(_verdict_ids(continued.result.get(RESULT_VERDICT_IDS)))
    except ValueError:
        # Specific: malformed ids on the continued entry mean "cannot compare".
        return None


def _verdict_ids(raw: object) -> list[str]:
    if raw is None:
        return []
    items = cast(list[object], raw) if isinstance(raw, list) else None
    if items is None or not all(isinstance(item, str) for item in items):
        raise ValueError(f"the entry result's verdict ids are malformed: {raw!r}")
    return [item for item in items if isinstance(item, str)]


def _attempts(store: Store, node_id: str, step: str | None) -> int | None:
    """Counted attempts for a known step; ``None`` when the step cannot be counted."""
    if step is None or step not in set(LifecycleStep):
        return None
    return store.attempt_count(node_id, step)


def _read_parts(
    store: Store, verdict_ids: Sequence[str]
) -> tuple[ReviewPart, ...] | None:
    """One part per verdict, or ``None`` when any of them cannot be read back."""
    parts: list[ReviewPart] = []
    for verdict_id in verdict_ids:
        part = _read_part(store, verdict_id)
        if part is None:
            return None
        parts.append(part)
    return tuple(parts)


def _read_part(store: Store, verdict_id: str) -> ReviewPart | None:
    record = store.verdict(verdict_id)
    if record is None:
        return None
    try:
        observations = store.observations(verdict_id)
        changes = store.finding_changes(verdict_id)
    except VerdictNotFoundError:
        # D5: a verdict that vanished between the lookup and the reads is an
        # unreadable review, which routes as unknown rather than faulting the
        # project on every tick.
        return None
    highest = max(
        (found.severity for found in observations),
        key=SEVERITY_LOW_TO_HIGH.index,
        default=FindingSeverity.PASS,
    )
    return ReviewPart(
        verdict=record.verdict,
        standing=record.standing,
        severity=highest,
        comparable=changes.comparable,
        routed_changes=tuple(
            tagged.change
            for tagged in changes.findings
            if tagged.observation.severity in ROUTED_SEVERITIES
        ),
    )
