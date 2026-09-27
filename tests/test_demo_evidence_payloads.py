"""The walkthrough's review payloads use only real, captured Squadron text."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from review_fixtures import SQ_REVIEWS, review_findings

from amoeba.inbox.evidence_payloads import FindingPayload

PAYLOAD_DIR = Path(__file__).parent.parent / "scripts" / "demo_evidence"

_CAPTURED_SUMMARIES = {
    finding.summary
    for path in SQ_REVIEWS.glob("*.md")
    for finding in review_findings(path)
}


@pytest.mark.parametrize(
    "payload_file", sorted(PAYLOAD_DIR.glob("*.json")), ids=lambda p: p.name
)
def test_every_payload_summary_is_captured_text(payload_file: Path) -> None:
    entries: list[dict[str, object]] = json.loads(payload_file.read_text())
    assert entries
    for entry in entries:
        FindingPayload.model_validate(entry)
        assert entry["summary"] in _CAPTURED_SUMMARIES, entry["summary"]
