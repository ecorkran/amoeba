"""Paths to the captured Squadron review fixtures in ``tests/fixtures/sq_reviews/``.

Paths only. Reading them is the job of ``amoeba.upstream.squadron``, so tests read
what production reads.
"""

from __future__ import annotations

from pathlib import Path

SQ_REVIEWS = Path(__file__).parent / "fixtures" / "sq_reviews"

_REVIEW_STEM = "102-review.tasks.resident-process-and-recovery"
ROUND_1_PART_1 = SQ_REVIEWS / f"{_REVIEW_STEM}.part-1.20260921T112529.md"
ROUND_1_PART_2 = SQ_REVIEWS / f"{_REVIEW_STEM}.part-2.20260921T112635.md"
ROUND_2_PART_1 = SQ_REVIEWS / f"{_REVIEW_STEM}.part-1.md"
ROUND_2_PART_2 = SQ_REVIEWS / f"{_REVIEW_STEM}.part-2.md"

PROVIDER_FAILURE_928 = SQ_REVIEWS / (
    "928-review.slice.codex-parity-for-skill-packs-and-provider-access"
    ".20260927T212759.md"
)
FINDINGS_NOT_PARSED_925 = SQ_REVIEWS / (
    "925-review.code.command-install-target-parity-codex-via-the-agents-skill-layout"
    ".20260922T145229.md"
)
FINDINGS_NOT_PARSED_EDITED = SQ_REVIEWS / (
    "102-review.tasks.resident-process-and-recovery.part-1.20260921T112529"
    ".findings-not-parsed-edited.md"
)
PR_REVIEW_116 = SQ_REVIEWS / "github.com-ecorkran-squadron-116-review.code.md"
STAMPED_REVIEW_106 = SQ_REVIEWS / (
    "106-review.slice.outbound-change-feed-and-detection-of-external-work"
    ".20260928T175751.md"
)

_PAIR_STEM = "105-review.slice.squadron-review-parser-and-ingest.20261015T041112"
#: One real review captured both ways: the saved file and its stdout JSON.
PAIR_ARTIFACT = SQ_REVIEWS / f"{_PAIR_STEM}.md"
PAIR_STDOUT = SQ_REVIEWS / f"{_PAIR_STEM}.stdout.json"
