"""Rows for the ``checks`` and ``calibration`` listings.

A sibling of ``inspect_evidence.py``: this module holds the columns and the row
functions, and ``inspect.py`` registers them in its one ``LISTINGS`` registry
(registering needs ``Listing``, which lives there). Both receive a **read-only**
store, so they work whether or not the resident process is running.
"""

from __future__ import annotations

from typing import Final

from amoeba.inspection.listing import NODE_OPTION, ListingRequest, Row
from amoeba.store import Store
from amoeba.store.calibration import CALIBRATION_COLUMNS

CHECK_COLUMNS: Final = (
    "recorded_seq",
    "id",
    "node_id",
    "name",
    "outcome",
    "examined_count",
    "standing",
    "baseline_ref",
    "upstream_version",
)

#: The D3 names, from their one definition beside ``CalibrationRow``.
CALIBRATION_LISTING_COLUMNS: Final = tuple(column for _, column in CALIBRATION_COLUMNS)


def check_rows(store: Store, request: ListingRequest) -> list[Row]:
    """A project's checks in arrival order, optionally for one node."""
    return [
        {
            "recorded_seq": record.recorded_seq,
            "id": record.id,
            "node_id": record.node_id,
            "name": record.name,
            "outcome": record.outcome.value,
            "examined_count": record.examined_count,
            "standing": record.standing.value,
            "baseline_ref": record.baseline_ref,
            "upstream_version": record.provenance.upstream_version,
            "upstream": record.provenance.upstream,
            "source": record.provenance.source.value,
            "source_path": record.provenance.source_path or "",
            "examined": None if record.examined is None else dict(record.examined),
            "recorded_at": record.recorded_at.isoformat(),
        }
        for record in store.checks(
            request.require_project_id(), node_id=request.option(NODE_OPTION)
        )
    ]


def calibration_rows(store: Store, request: ListingRequest) -> list[Row]:
    """One row per ``(review_type, model)`` over a project's judge samples."""
    return [
        {column: getattr(row, field) for field, column in CALIBRATION_COLUMNS}
        for row in store.calibration(request.require_project_id())
    ]
