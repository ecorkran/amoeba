"""Parse Squadron review output into a ``ParsedReview``.

Pure: no I/O, no store, no inbox. Callers in the CLI, the detection tenant, and
the Runner all use the same readers and the same composition.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from amoeba.store.evidence_models import (
    FindingInput,
    RecordSource,
    ReviewVerdict,
    VerdictDerivation,
)


class SquadronReviewError(ValueError):
    """Base for every error raised while reading or composing a Squadron review."""


class SquadronParseError(SquadronReviewError):
    """The input could not be read as a review; the message names the problem."""

    def __init__(self, source: RecordSource, message: str) -> None:
        super().__init__(f"{source.value}: {message}")
        self.source = source


class UpstreamVersionError(SquadronReviewError):
    """No usable version label, or the stamp and the caller's label disagree."""


@dataclass(frozen=True, kw_only=True)
class ParsedReview:
    """One review as Squadron reported it, before the caller adds node and path.

    ``upstream_version`` is Squadron's own stamp (``None`` on older output).
    ``slice`` and ``source_document`` are read from files only; they are kept for
    the record id and for callers, and are not part of ``VerdictInput``.
    """

    verdict: ReviewVerdict
    derivation: VerdictDerivation
    fallback_used: bool | None
    findings_parsed: bool | None
    provider_failure: bool
    review_type: str
    model: str
    requested_model: str | None
    diff_truncated: bool | None
    reviewed_sha: str | None
    tool_calls_made: int | None
    score: float | None
    criteria: Mapping[str, object] | None
    sq_run_id: str | None
    findings: tuple[FindingInput, ...]
    source: RecordSource
    upstream_version: str | None
    slice: str | None
    source_document: str | None
