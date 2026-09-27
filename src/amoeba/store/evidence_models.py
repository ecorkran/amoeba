"""Closed vocabularies, transfer objects, and the trust label for review evidence.

Every verdict and finding vocabulary value is defined here and nowhere else.
Like ``models.py``, this module knows nothing about SQL or ``sqlite3``.

The trust label (``VerdictStanding``) is computed from stored fields by
``verdict_standing`` and never stored, so changing the rule needs no data fix.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Final


class ReviewVerdict(StrEnum):
    PASS = "PASS"
    CONCERNS = "CONCERNS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"


class FindingSeverity(StrEnum):
    PASS = "pass"
    NOTE = "note"
    CONCERN = "concern"
    FAIL = "fail"


class VerdictDerivation(StrEnum):
    """How the verdict was reached; ``not_reported`` when the input did not say."""

    STATED = "stated"
    DERIVED = "derived"
    IMPOSED = "imposed"
    NOT_REPORTED = "not_reported"


class RecordSource(StrEnum):
    """Which Squadron output the caller read the verdict from."""

    STDOUT_JSON = "stdout_json"
    ARTIFACT_FRONTMATTER = "artifact_frontmatter"


class FindingChange(StrEnum):
    NEW = "new"
    RECURRING = "recurring"
    GONE = "gone"


class VerdictStanding(StrEnum):
    """The trust label: what kind of verdict this is, not whether to act on it."""

    PROVIDER_FAILURE = "provider_failure"
    UNPARSED = "unparsed"
    FINDINGS_UNPARSED = "findings_unparsed"
    IMPOSED = "imposed"
    DERIVED = "derived"
    UNATTESTED = "unattested"
    STATED = "stated"


#: Standings whose findings may serve as, or be compared with, a previous round.
#: A failed round is never a baseline, or it would report every finding as gone.
COMPARABLE_STANDINGS: Final = frozenset(
    {
        VerdictStanding.STATED,
        VerdictStanding.DERIVED,
        VerdictStanding.IMPOSED,
        VerdictStanding.UNATTESTED,
    }
)


def parse_verdict(text: str) -> ReviewVerdict:
    """Accept a verdict in any letter case; raise ``ValueError`` on an unknown word."""
    try:
        return ReviewVerdict(text.strip().upper())
    except ValueError:
        raise ValueError(f"unknown verdict: {text!r}") from None


def parse_severity(text: str) -> FindingSeverity:
    """Accept a severity in any letter case; raise ``ValueError`` on an unknown word."""
    try:
        return FindingSeverity(text.strip().lower())
    except ValueError:
        raise ValueError(f"unknown severity: {text!r}") from None


def verdict_standing(
    *,
    provider_failure: bool,
    verdict: ReviewVerdict,
    findings_parsed: bool | None,
    derivation: VerdictDerivation,
) -> VerdictStanding:
    """The one trust-label rule, checked top to bottom.

    Reads ``derivation`` and ``findings_parsed``, never ``fallback_used``: the
    caller maps Squadron's flags onto those two fields.
    """
    if provider_failure:
        return VerdictStanding.PROVIDER_FAILURE
    if verdict is ReviewVerdict.UNKNOWN:
        return VerdictStanding.UNPARSED
    if findings_parsed is False:
        return VerdictStanding.FINDINGS_UNPARSED
    if derivation is VerdictDerivation.IMPOSED:
        return VerdictStanding.IMPOSED
    if derivation is VerdictDerivation.DERIVED:
        return VerdictStanding.DERIVED
    if derivation is VerdictDerivation.NOT_REPORTED:
        return VerdictStanding.UNATTESTED
    return VerdictStanding.STATED


@dataclass(frozen=True, kw_only=True)
class Provenance:
    """Where a verdict came from. ``upstream_version`` is a label, never compared."""

    upstream: str
    upstream_version: str
    source: RecordSource
    source_path: str | None = None


@dataclass(frozen=True, kw_only=True)
class FindingInput:
    """One finding as the reviewer gave it. ``position_id`` is data only."""

    severity: FindingSeverity
    summary: str
    position_id: str | None = None
    category: str | None = None
    location: str | None = None


@dataclass(frozen=True, kw_only=True)
class VerdictInput:
    """One review result, already parsed by the caller.

    ``derivation``, ``fallback_used``, and ``findings_parsed`` have no default:
    "not reported" must be said explicitly.
    """

    id: str
    node_id: str
    verdict: ReviewVerdict
    derivation: VerdictDerivation
    fallback_used: bool | None
    findings_parsed: bool | None
    provider_failure: bool
    review_type: str
    model: str
    findings: tuple[FindingInput, ...]
    provenance: Provenance
    diff_truncated: bool | None = None
    requested_model: str | None = None
    reviewed_sha: str | None = None
    score: float | None = None
    criteria: Mapping[str, object] | None = None
    tool_calls_made: int | None = None
    sq_run_id: str | None = None
    journal_entry_id: str | None = None


@dataclass(frozen=True, kw_only=True)
class VerdictRecord(VerdictInput):
    """A recorded verdict. ``recorded_seq`` is arrival order."""

    project_id: str
    recorded_seq: int
    recorded_at: datetime

    @property
    def standing(self) -> VerdictStanding:
        return verdict_standing(
            provider_failure=self.provider_failure,
            verdict=self.verdict,
            findings_parsed=self.findings_parsed,
            derivation=self.derivation,
        )


@dataclass(frozen=True, kw_only=True)
class FindingObservation:
    """One finding as stored for one review, with its content key."""

    verdict_id: str
    ordinal: int
    severity: FindingSeverity
    summary: str
    position_id: str | None
    category: str | None
    location: str | None
    normalized_location: str
    normalized_summary: str
    identity: str
    identity_version: int


@dataclass(frozen=True, kw_only=True)
class FindingSummary:
    """One content key on one node, across every review that reported it."""

    node_id: str
    identity: str
    identity_version: int
    latest_severity: FindingSeverity
    latest_summary: str
    latest_location: str | None
    first_verdict_id: str
    last_verdict_id: str
    times_seen: int


@dataclass(frozen=True, kw_only=True)
class TaggedFinding:
    observation: FindingObservation
    change: FindingChange


@dataclass(frozen=True, kw_only=True)
class FindingChanges:
    """What changed since the previous comparable round.

    ``gone`` holds the previous round's observations whose keys the target
    lacks. A target that is not comparable has no previous round and empty
    ``findings`` and ``gone``.
    """

    verdict_id: str
    comparable: bool
    previous_verdict_id: str | None
    findings: tuple[TaggedFinding, ...]
    gone: tuple[FindingObservation, ...]
