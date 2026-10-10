"""Every Squadron key name and literal this package reads, defined once.

Squadron owns these names; Amoeba reads them. Nothing else under
``amoeba.upstream.squadron`` spells one as a string literal, so a rename upstream
is a one-file change here. Derivation and source literals are not Squadron's:
use ``VerdictDerivation`` and ``RecordSource`` from ``amoeba.store.evidence_models``.

Keys Squadron writes that are dropped on purpose have no constant:
``location_verified``, ``finding_scan``, ``diff_chars``, ``diff_chars_injected``,
``answering_models``, ``stop_reason``, ``tools_given``.
"""

from __future__ import annotations

from typing import Final

# Stdout JSON top-level keys (`sq review ... --output json`).
JSON_VERDICT: Final = "verdict"
JSON_VERDICT_SOURCE: Final = "verdictSource"
JSON_FALLBACK_USED: Final = "fallback_used"
JSON_STRUCTURED_FINDINGS: Final = "structured_findings"
JSON_TEMPLATE_NAME: Final = "template_name"
JSON_MODEL: Final = "model"
JSON_REQUESTED_MODEL: Final = "requested_model"
JSON_MODEL_SUBSTITUTED: Final = "model_substituted"
JSON_DIFF_TRUNCATED: Final = "diff_truncated"
JSON_SCORE: Final = "score"
JSON_CRITERIA: Final = "criteria"
JSON_TOOL_CALLS_MADE: Final = "tool_calls_made"
JSON_RUN_ID: Final = "run_id"
JSON_SQUADRON_VERSION: Final = "squadron_version"

# Review-file frontmatter keys.
FM_REVIEW_TYPE: Final = "reviewType"
FM_VERDICT: Final = "verdict"
FM_VERDICT_SOURCE: Final = "verdictSource"
FM_AI_MODEL: Final = "aiModel"
FM_REQUESTED_MODEL: Final = "requestedModel"
FM_DIFF_TRUNCATED: Final = "diffTruncated"
FM_REVIEWED_SHA: Final = "reviewedSha"
FM_TOOL_CALLS_MADE: Final = "toolCallsMade"
FM_SCORE: Final = "score"
FM_CRITERIA: Final = "criteria"
FM_RUN_ID: Final = "runId"
FM_SQUADRON_VERSION: Final = "squadronVersion"
FM_SLICE: Final = "slice"
FM_SOURCE_DOCUMENT: Final = "sourceDocument"
FM_PROVIDER_FAILURE: Final = "providerFailure"
FM_FINDINGS: Final = "findings"

# Finding keys, the same in both sources.
FINDING_ID: Final = "id"
FINDING_SEVERITY: Final = "severity"
FINDING_CATEGORY: Final = "category"
FINDING_SUMMARY: Final = "summary"
FINDING_LOCATION: Final = "location"

# Body headings, text only (any `#` level, any case).
HEADING_PROVIDER_FAILURE: Final = "Provider Failure"
HEADING_FINDINGS_NOT_PARSED: Final = "Findings Not Parsed"

# Other literals.
UPSTREAM_NAME: Final = "squadron"
RECORD_ID_FORMAT_TAG: Final = "parsed-review-v1"
