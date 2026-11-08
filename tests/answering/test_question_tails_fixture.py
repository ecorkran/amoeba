"""The walkthrough's captured question tails are well formed (slice 145, D8)."""

from __future__ import annotations

import json
from pathlib import Path

TAILS = (
    Path(__file__).parents[1]
    / "live"
    / "answering"
    / "fixtures"
    / "question_tails.json"
)
KEYS = ("question", "run_id", "captured", "source")


def test_every_captured_tail_has_its_four_fields() -> None:
    entries: list[dict[str, str]] = json.loads(TAILS.read_text(encoding="utf-8"))

    assert entries
    for entry in entries:
        assert set(entry) == set(KEYS)
        assert all(entry[key].strip() for key in KEYS), entry
