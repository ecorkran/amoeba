"""``review_record_id``: stable for the same parsed content, sensitive to changes."""

from __future__ import annotations

import dataclasses
import re

from review_fixtures import ROUND_1_PART_1, STAMPED_REVIEW_106

from amoeba.store.evidence_models import ReviewVerdict
from amoeba.upstream.squadron import parse_review_artifact, review_record_id

EXPECTED_ROUND_1_PART_1_ID = "sq-review-e1e00506963fd2f2aec41439b8ba3261"


def _text() -> str:
    return ROUND_1_PART_1.read_text(encoding="utf-8")


def test_the_id_is_a_prefixed_32_hex_digest() -> None:
    record_id = review_record_id(parse_review_artifact(_text()))
    assert re.fullmatch(r"sq-review-[0-9a-f]{32}", record_id)


def test_the_same_content_gives_the_same_id() -> None:
    assert review_record_id(parse_review_artifact(_text())) == review_record_id(
        parse_review_artifact(_text())
    )


def test_hand_added_resolution_keys_and_a_response_section_keep_the_id() -> None:
    edited = _text().replace(
        "findings:\n", "resolution: fixed\nresolvedBy: someone\nfindings:\n", 1
    )
    edited += "\n## Response\n\nAddressed in the next commit.\n"
    assert edited != _text()
    assert review_record_id(parse_review_artifact(edited)) == review_record_id(
        parse_review_artifact(_text())
    )


def test_a_changed_finding_summary_changes_the_id() -> None:
    parsed = parse_review_artifact(_text())
    first, *rest = parsed.findings
    reworded = dataclasses.replace(first, summary=first.summary + " (reworded)")
    changed = dataclasses.replace(parsed, findings=(reworded, *rest))
    assert review_record_id(changed) != review_record_id(parsed)


def test_a_changed_verdict_changes_the_id() -> None:
    parsed = parse_review_artifact(_text())
    changed = dataclasses.replace(parsed, verdict=ReviewVerdict.FAIL)
    assert review_record_id(changed) != review_record_id(parsed)


def test_a_changed_finding_order_changes_the_id() -> None:
    parsed = parse_review_artifact(STAMPED_REVIEW_106.read_text(encoding="utf-8"))
    swapped = dataclasses.replace(parsed, findings=parsed.findings[::-1])
    assert review_record_id(swapped) != review_record_id(parsed)


def test_the_id_is_pinned_for_a_real_file() -> None:
    # A literal on purpose: a change here is a contract change (new format tag,
    # CHANGELOG entry), not a refactor.
    parsed = parse_review_artifact(_text())
    assert review_record_id(parsed) == EXPECTED_ROUND_1_PART_1_ID
