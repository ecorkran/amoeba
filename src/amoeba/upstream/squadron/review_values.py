"""Value readers shared by the stdout reader and the review-file reader.

Each takes the raw mapping, the key, and the ``RecordSource`` it came from, and
raises ``SquadronParseError`` naming the key. Nothing is defaulted.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, NoReturn, cast

from amoeba.store.evidence_models import (
    FindingInput,
    RecordSource,
    ReviewVerdict,
    VerdictDerivation,
    parse_severity,
    parse_verdict,
)
from amoeba.upstream.squadron import review_fields as fields
from amoeba.upstream.squadron.review import SquadronParseError


def fail(source: RecordSource, message: str) -> NoReturn:
    raise SquadronParseError(source, message)


def typed[ValueT](
    raw: Mapping[str, Any], key: str, kind: type[ValueT], source: RecordSource
) -> ValueT | None:
    """The value at ``key``, or ``None`` if absent or null. A wrong type raises."""
    value = raw.get(key)
    if value is None:
        return None
    # bool is an int subclass; a flag where a number is expected is a mistake.
    if not isinstance(value, kind) or (isinstance(value, bool) and kind is not bool):
        fail(source, f"{key!r} has the wrong type: {value!r}")
    return cast(ValueT, value)


def number(raw: Mapping[str, Any], key: str, source: RecordSource) -> float | None:
    value = raw.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int | float):
        fail(source, f"{key!r} is not a number: {value!r}")
    return float(value)


def required(raw: Mapping[str, Any], key: str, source: RecordSource) -> str:
    value = typed(raw, key, str, source)
    if value is None or not value.strip():
        fail(source, f"missing required key {key!r}")
    return value


def read_verdict(
    raw: Mapping[str, Any], key: str, source: RecordSource
) -> ReviewVerdict:
    word = required(raw, key, source)
    try:
        return parse_verdict(word)
    except ValueError as error:
        raise SquadronParseError(source, str(error)) from error


def read_derivation(
    raw: Mapping[str, Any], key: str, source: RecordSource
) -> VerdictDerivation:
    word = typed(raw, key, str, source)
    if word is None:
        return VerdictDerivation.NOT_REPORTED
    try:
        return VerdictDerivation(word.strip().lower())
    except ValueError:
        fail(source, f"{key!r}: unknown value {word!r}")


def read_criteria(
    raw: Mapping[str, Any], key: str, source: RecordSource
) -> Mapping[str, object] | None:
    value = raw.get(key)
    if value is None:
        return None
    if not isinstance(value, dict):
        fail(source, f"{key!r} has the wrong type: {value!r}")
    return cast(dict[str, object], value)


def read_findings(
    items: object, key: str, source: RecordSource
) -> tuple[FindingInput, ...]:
    if items is None:
        return ()
    if not isinstance(items, list):
        fail(source, f"{key!r} is not a list")
    return tuple(
        read_finding(item, f"{key}[{index}]", source)
        for index, item in enumerate(cast(list[object], items))
    )


def read_finding(item: object, label: str, source: RecordSource) -> FindingInput:
    """One finding, identical in both sources. Missing severity or summary raises."""
    if not isinstance(item, dict):
        fail(source, f"{label} is not a mapping")
    raw = cast(dict[str, Any], item)
    severity_word = raw.get(fields.FINDING_SEVERITY)
    if not isinstance(severity_word, str):
        fail(source, f"{label} has no {fields.FINDING_SEVERITY!r}")
    try:
        severity = parse_severity(severity_word)
    except ValueError as error:
        raise SquadronParseError(source, f"{label}: {error}") from error
    summary = raw.get(fields.FINDING_SUMMARY)
    if not isinstance(summary, str) or not summary.strip():
        fail(source, f"{label} has no {fields.FINDING_SUMMARY!r}")
    return FindingInput(
        position_id=typed(raw, fields.FINDING_ID, str, source),
        severity=severity,
        category=typed(raw, fields.FINDING_CATEGORY, str, source),
        summary=summary,
        location=typed(raw, fields.FINDING_LOCATION, str, source),
    )
