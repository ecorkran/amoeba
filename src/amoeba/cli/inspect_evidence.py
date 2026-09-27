"""Rows for the evidence listings: ``verdicts`` and ``findings``.

A sibling of ``inspect.py``, which registers these in its one ``LISTINGS``
registry. Both receive a **read-only** store, so they work whether or not the
resident process is running.

``findings --verdict ID`` is the one listing with a header: in table form it
prints a line naming the previous round (or saying the review is not
comparable) before the rows. In JSON form every row carries
``previous_verdict_id`` instead, so the output stays one JSON array.
"""

from __future__ import annotations

import argparse
from typing import TYPE_CHECKING, Final

from amoeba.store import FindingChange, FindingChanges, FindingObservation, Store

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
    "change",
    "node_id",
    "severity",
    "summary",
    "location",
    "times_seen",
    "first_verdict_id",
    "last_verdict_id",
    "key",
)

#: Enough of the hex key to tell keys apart by eye; JSON carries the full key.
_SHORT_KEY_LENGTH: Final = 12


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
    """One row per key, or with ``--verdict``, that review's changes.

    Raises:
        VerdictNotFoundError: For an unknown ``--verdict`` id, which the CLI
            boundary reports as an error, never as an empty listing.
    """
    if args.verdict is not None:
        return _change_rows(store.finding_changes(args.verdict), use_json=args.json)
    return [
        {
            "change": "",
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


def _change_rows(changes: FindingChanges, *, use_json: bool) -> list[Row]:
    if not use_json:
        print(_header(changes))
    tagged = [(t.change, t.observation) for t in changes.findings]
    tagged += [(FindingChange.GONE, observation) for observation in changes.gone]
    return [
        _change_row(change, observation, changes, use_json=use_json)
        for change, observation in tagged
    ]


def _header(changes: FindingChanges) -> str:
    if not changes.comparable:
        return f"verdict {changes.verdict_id}: not comparable"
    previous = changes.previous_verdict_id or "none"
    return f"verdict {changes.verdict_id}: previous review {previous}"


def _change_row(
    change: FindingChange,
    observation: FindingObservation,
    changes: FindingChanges,
    *,
    use_json: bool,
) -> Row:
    row: Row = {
        "change": change.value,
        "severity": observation.severity.value,
        "summary": observation.summary,
        "location": observation.location or "",
        "key": _key(observation.identity, use_json=use_json),
        "verdict_id": observation.verdict_id,
    }
    if use_json:
        row["previous_verdict_id"] = changes.previous_verdict_id
    return row


def _key(identity: str, *, use_json: bool) -> str:
    return identity if use_json else identity[:_SHORT_KEY_LENGTH]
