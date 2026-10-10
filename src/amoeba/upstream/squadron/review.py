"""Parse Squadron review output into a ``ParsedReview``.

Pure: no I/O, no store, no inbox. Callers in the CLI, the detection tenant, and
the Runner all use the same readers and the same composition.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass

from amoeba.store.evidence_models import (
    FindingInput,
    Provenance,
    RecordSource,
    ReviewVerdict,
    VerdictDerivation,
    VerdictInput,
)
from amoeba.upstream.squadron import review_fields as fields


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


_RECORD_ID_PREFIX = "sq-review-"
_RECORD_ID_HEX_LENGTH = 32


def review_record_id(parsed: ParsedReview) -> str:
    """A stable id: a digest of the parsed review, not of its bytes (D5).

    The digest covers every ``ParsedReview`` field and nothing the caller supplies
    (node, path, version label, journal entry), so a hand edit that adds
    ``resolution:`` keeps the id. Changing the covered fields changes every id, so
    it needs a new ``RECORD_ID_FORMAT_TAG`` and a CHANGELOG entry.
    """
    # Enum members are str subclasses, so json encodes each by its value.
    canonical = json.dumps(
        [fields.RECORD_ID_FORMAT_TAG, asdict(parsed)],
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return _RECORD_ID_PREFIX + digest[:_RECORD_ID_HEX_LENGTH]


def _resolve_version(stamp: str | None, supplied: str | None) -> str:
    """D4: Squadron's stamp, else the caller's label; the two may not disagree."""
    if stamp is None and supplied is None:
        raise UpstreamVersionError(
            "no upstream version: the review carries no stamp and none was supplied"
        )
    if stamp is not None and supplied is not None and stamp != supplied:
        raise UpstreamVersionError(
            f"the review is stamped {stamp!r} but {supplied!r} was supplied"
        )
    return stamp if stamp is not None else str(supplied)


def to_verdict_input(
    parsed: ParsedReview,
    *,
    node_id: str,
    record_id: str | None = None,
    upstream_version: str | None = None,
    journal_entry_id: str | None = None,
    source_path: str | None = None,
) -> VerdictInput:
    """Compose the store input from a parsed review and the caller's values."""
    return VerdictInput(
        id=record_id if record_id is not None else review_record_id(parsed),
        node_id=node_id,
        verdict=parsed.verdict,
        derivation=parsed.derivation,
        fallback_used=parsed.fallback_used,
        findings_parsed=parsed.findings_parsed,
        provider_failure=parsed.provider_failure,
        review_type=parsed.review_type,
        model=parsed.model,
        findings=parsed.findings,
        provenance=Provenance(
            upstream=fields.UPSTREAM_NAME,
            upstream_version=_resolve_version(
                parsed.upstream_version, upstream_version
            ),
            source=parsed.source,
            source_path=source_path,
        ),
        diff_truncated=parsed.diff_truncated,
        requested_model=parsed.requested_model,
        reviewed_sha=parsed.reviewed_sha,
        score=parsed.score,
        criteria=parsed.criteria,
        tool_calls_made=parsed.tool_calls_made,
        sq_run_id=parsed.sq_run_id,
        journal_entry_id=journal_entry_id,
    )
