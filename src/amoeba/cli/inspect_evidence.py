"""Rows for the evidence listings: ``verdicts``, ``findings``, and ``changes``.

A sibling of ``inspect.py``, which registers these in its one ``LISTINGS``
registry. All receive a **read-only** store, so they work whether or not the
resident process is running.

``changes --verdict ID`` refuses a review that is not comparable rather than
printing no rows, so neither output form can pass a failed round off as a
round with nothing in it.
"""

from __future__ import annotations

import argparse
from typing import TYPE_CHECKING, Final

from amoeba.store import FindingChange, FindingObservation, Store

if TYPE_CHECKING:  # pragma: no cover - typing only; inspect.py imports this
    from amoeba.cli.inspect import Row

VERDICT_COLUMNS: Final = (
    "recorded_seq",
    "id",
    "node_id",
    "review_type",
    "model",
    "verdict",
    "standing",
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


def verdict_rows(store: Store, args: argparse.Namespace) -> list[Row]:
    """A project's verdicts in arrival order, optionally for one node."""
    return [
        {
            "recorded_seq": record.recorded_seq,
            "id": record.id,
            "node_id": record.node_id,
            "review_type": record.review_type,
            "model": record.model,
            "verdict": record.verdict.value,
            "standing": record.standing.value,
            "upstream_version": record.provenance.upstream_version,
            "upstream": record.provenance.upstream,
            "source": record.provenance.source.value,
            "source_path": record.provenance.source_path or "",
            "recorded_at": record.recorded_at.isoformat(),
        }
        for record in store.verdicts(args.project, node_id=args.node)
    ]


def finding_rows(store: Store, args: argparse.Namespace) -> list[Row]:
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
            "key": _key(summary.identity, use_json=args.json),
        }
        for summary in store.findings(args.project, node_id=args.node)
    ]


def change_rows(store: Store, args: argparse.Namespace) -> list[Row]:
    """One review's findings tagged new or recurring, plus the ones now gone.

    Raises:
        VerdictNotFoundError: For an unknown ``--verdict`` id.
        VerdictNotComparableError: When the review is not comparable.
    """
    changes = store.finding_changes(args.verdict)
    if not changes.comparable:
        raise VerdictNotComparableError(changes.verdict_id)
    tagged = [(t.change, t.observation) for t in changes.findings]
    tagged += [(FindingChange.GONE, observation) for observation in changes.gone]
    return [
        _change_row(change, observation, changes.previous_verdict_id, args.json)
        for change, observation in tagged
    ]


def _change_row(
    change: FindingChange,
    observation: FindingObservation,
    previous_verdict_id: str | None,
    use_json: bool,
) -> Row:
    return {
        "change": change.value,
        "severity": observation.severity.value,
        "summary": observation.summary,
        "location": observation.location or "",
        "key": _key(observation.identity, use_json=use_json),
        "previous_verdict_id": previous_verdict_id,
        "verdict_id": observation.verdict_id,
    }


def _key(identity: str, *, use_json: bool) -> str:
    return identity if use_json else identity[:_SHORT_KEY_LENGTH]
