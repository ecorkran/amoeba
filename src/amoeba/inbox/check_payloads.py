"""Pydantic payload model for the ``check`` submission kind.

Field names are the payload keys defined once in ``amoeba.store.check_models``;
a test pins the two together. ``outcome`` and ``source`` use the store's word
lists, so an unknown word fails validation and the file is quarantined.

``examined_count`` has no default: a submitter says ``null`` ("not reported")
rather than leaving it out, as ``findings_parsed`` works for verdicts.
"""

from __future__ import annotations

from pydantic import BaseModel

from amoeba.inbox.payload_config import MODEL_CONFIG
from amoeba.store.check_models import CheckOutcome
from amoeba.store.evidence_models import RecordSource


class CheckPayload(BaseModel):
    """One check result; the submission id becomes the record id."""

    model_config = MODEL_CONFIG

    node_id: str
    name: str
    outcome: CheckOutcome
    examined_count: int | None
    upstream: str
    upstream_version: str
    source: RecordSource
    examined: dict[str, object] | None = None
    baseline_ref: str | None = None
    source_path: str | None = None
