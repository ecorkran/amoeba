"""Rows for the evidence listings: ``verdicts``, ``findings``, and ``changes``.

A sibling of ``inspect.py``, which registers these in its one ``LISTINGS``
registry. All receive a **read-only** store, so they work whether or not the
resident process is running.

``changes --verdict ID`` refuses a review that is not comparable rather than
printing no rows, so neither output form can pass a failed round off as a
round with nothing in it.
"""

from __future__ import annotations

from typing import Final

from amoeba.inspection.listing import NODE_OPTION, ListingRequest, Row, ValueOption
from amoeba.store import FindingChange, FindingObservation, Store

JUDGE_INVOCATION_OPTION = ValueOption(
    name="judge_invocation_id",
    help_text="Only this judge invocation's samples.",
    metavar="ID",
)

VERDICT_OPTION = ValueOption(
    name="verdict",
    help_text="The review to compare with its previous round.",
    metavar="ID",
    required=True,
)

VERDICT_COLUMNS: Final = (
    "recorded_seq",
    "id",
    "node_id",
    "review_type",
    "model",
    "verdict",
    "standing",
    "judge_invocation_id",
    "upstream_version",
)

FINDING_COLUMNS: Final = (
    "node_id",
    "severity",
    "summary",
    "location",
    "times_seen",
    "first_verdict_id",
    "last_verdict_id",
    "key",
)

CHANGE_COLUMNS: Final = (
    "change",
    "severity",
    "summary",
    "location",
    "key",
    "previous_verdict_id",
)

#: Enough of the hex key to tell keys apart by eye; JSON carries the full key.
_SHORT_KEY_LENGTH: Final = 12


class VerdictNotComparableError(Exception):
    """The review's standing means its findings cannot be compared to another's."""

    def __init__(self, verdict_id: str) -> None:
        super().__init__(
            f"verdict {verdict_id!r} is not comparable (failed or unparsed review)"
        )


def verdict_rows(store: Store, request: ListingRequest) -> list[Row]:
    """A project's verdicts in arrival order, optionally for a node or invocation."""
    return [
        {
            "recorded_seq": record.recorded_seq,
            "id": record.id,
            "node_id": record.node_id,
            "review_type": record.review_type,
            "model": record.model,
            "verdict": record.verdict.value,
            "standing": record.standing.value,
            "judge_invocation_id": record.judge_invocation_id,
            "upstream_version": record.provenance.upstream_version,
            "upstream": record.provenance.upstream,
            "source": record.provenance.source.value,
            "source_path": record.provenance.source_path or "",
            "sq_run_id": record.sq_run_id,
            "reviewed_sha": record.reviewed_sha,
            "recorded_at": record.recorded_at.isoformat(),
        }
        for record in store.verdicts(
            request.require_project_id(),
            node_id=request.option(NODE_OPTION),
            judge_invocation_id=request.option(JUDGE_INVOCATION_OPTION),
        )
    ]


def finding_rows(store: Store, request: ListingRequest) -> list[Row]:
    """One row per content key, optionally for one node."""
    return [
        {
            "node_id": summary.node_id,
            "severity": summary.latest_severity.value,
            "summary": summary.latest_summary,
            "location": summary.latest_location or "",
            "times_seen": summary.times_seen,
            "first_verdict_id": summary.first_verdict_id,
            "last_verdict_id": summary.last_verdict_id,
            "key": _key(summary.identity, compact=request.compact),
        }
        for summary in store.findings(
            request.require_project_id(), node_id=request.option(NODE_OPTION)
        )
    ]


def change_rows(store: Store, request: ListingRequest) -> list[Row]:
    """One review's findings tagged new or recurring, plus the ones now gone.

    Raises:
        VerdictNotFoundError: For an unknown ``--verdict`` id.
        VerdictNotComparableError: When the review is not comparable.
        ValueError: When the request carries no verdict id.
    """
    verdict_id = request.option(VERDICT_OPTION)
    if verdict_id is None:
        raise ValueError("the changes listing requires a verdict id")
    changes = store.finding_changes(verdict_id)
    if not changes.comparable:
        raise VerdictNotComparableError(changes.verdict_id)
    tagged = [(t.change, t.observation) for t in changes.findings]
    tagged += [(FindingChange.GONE, observation) for observation in changes.gone]
    return [
        _change_row(change, observation, changes.previous_verdict_id, request.compact)
        for change, observation in tagged
    ]


def _change_row(
    change: FindingChange,
    observation: FindingObservation,
    previous_verdict_id: str | None,
    compact: bool,
) -> Row:
    return {
        "change": change.value,
        "severity": observation.severity.value,
        "summary": observation.summary,
        "location": observation.location or "",
        "key": _key(observation.identity, compact=compact),
        "previous_verdict_id": previous_verdict_id,
        "verdict_id": observation.verdict_id,
    }


def _key(identity: str, *, compact: bool) -> str:
    return identity[:_SHORT_KEY_LENGTH] if compact else identity
