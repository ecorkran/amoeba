"""Read the stdout of ``sq review ... --output json``."""

from __future__ import annotations

import json
from typing import Any, cast

from amoeba.store.evidence_models import RecordSource, VerdictDerivation
from amoeba.upstream.squadron import review_fields as fields
from amoeba.upstream.squadron.review import ParsedReview, SquadronParseError
from amoeba.upstream.squadron.review_values import (
    fail,
    number,
    read_criteria,
    read_derivation,
    read_findings,
    read_verdict,
    required,
    typed,
)

_JSON = RecordSource.STDOUT_JSON

# Where a stated or unreported verdict came out of Squadron's fallback path, the
# findings failed to parse; a derived verdict is not a parse failure.
_UNPARSED_WHEN_FALLBACK = frozenset(
    {VerdictDerivation.STATED, VerdictDerivation.NOT_REPORTED}
)


def _decode_first_object(text: str) -> dict[str, Any]:
    """Decode the first JSON object; text before and after it is ignored.

    Each ``{`` is tried in turn, so a stray brace in a preceding line does not
    hide the object. If none decodes, the first decode error is reported.
    """
    decoder = json.JSONDecoder()
    first_error: json.JSONDecodeError | None = None
    start = text.find("{")
    if start < 0:
        fail(_JSON, "no JSON object in the text")
    while start >= 0:
        try:
            decoded, _ = decoder.raw_decode(text, start)
            return cast(dict[str, Any], decoded)
        except json.JSONDecodeError as error:
            first_error = first_error or error
        start = text.find("{", start + 1)
    raise SquadronParseError(_JSON, f"malformed JSON: {first_error}") from first_error


def _findings_parsed(
    fallback_used: bool | None, derivation: VerdictDerivation
) -> bool | None:
    if fallback_used is None:
        return None
    return not (fallback_used and derivation in _UNPARSED_WHEN_FALLBACK)


def parse_review_json(text: str) -> ParsedReview:
    """Read Squadron's JSON stdout (D3, "From stdout JSON")."""
    raw = _decode_first_object(text)
    # A provider's error body is a JSON object with no verdict; name the key.
    if fields.JSON_VERDICT not in raw:
        fail(_JSON, f"missing required key {fields.JSON_VERDICT!r}")
    derivation = read_derivation(raw, fields.JSON_VERDICT_SOURCE, _JSON)
    fallback_used = typed(raw, fields.JSON_FALLBACK_USED, bool, _JSON)
    substituted = typed(raw, fields.JSON_MODEL_SUBSTITUTED, bool, _JSON) is True
    return ParsedReview(
        verdict=read_verdict(raw, fields.JSON_VERDICT, _JSON),
        derivation=derivation,
        fallback_used=fallback_used,
        findings_parsed=_findings_parsed(fallback_used, derivation),
        provider_failure=False,  # a failed provider call produces no JSON
        review_type=required(raw, fields.JSON_TEMPLATE_NAME, _JSON),
        model=required(raw, fields.JSON_MODEL, _JSON),
        # The contract sets it only on a substitution, as Squadron does in files.
        requested_model=(
            typed(raw, fields.JSON_REQUESTED_MODEL, str, _JSON) if substituted else None
        ),
        diff_truncated=typed(raw, fields.JSON_DIFF_TRUNCATED, bool, _JSON),
        reviewed_sha=None,  # not in the JSON
        tool_calls_made=typed(raw, fields.JSON_TOOL_CALLS_MADE, int, _JSON),
        score=number(raw, fields.JSON_SCORE, _JSON),
        criteria=read_criteria(raw, fields.JSON_CRITERIA, _JSON),
        sq_run_id=typed(raw, fields.JSON_RUN_ID, str, _JSON),
        findings=read_findings(
            raw.get(fields.JSON_STRUCTURED_FINDINGS),
            fields.JSON_STRUCTURED_FINDINGS,
            _JSON,
        ),
        source=_JSON,
        upstream_version=typed(raw, fields.JSON_SQUADRON_VERSION, str, _JSON),
        slice=None,
        source_document=None,  # JSON's input path is whatever the caller typed
    )
