"""D1's reductions for the four review inputs, over hand-built evidence."""

from __future__ import annotations

import pytest

from amoeba.runner.routing.inputs import NONE, UNKNOWN, RoutingInput
from amoeba.store import (
    FindingChange,
    FindingSeverity,
    ReviewVerdict,
    VerdictStanding,
)
from runner.routing.evidence_support import completed_evidence, part, value

REVIEW_INPUTS = (
    RoutingInput.VERDICT,
    RoutingInput.STANDING,
    RoutingInput.SEVERITY,
    RoutingInput.RECURRENCE,
)


def _all(evidence_changes: dict[str, object]) -> list[str]:
    evidence = completed_evidence(**evidence_changes)
    return [value(evidence, name) for name in REVIEW_INPUTS]


def test_no_review_is_none_throughout() -> None:
    assert _all({}) == [NONE] * 4


def test_a_review_fault_is_unknown_throughout() -> None:
    assert _all({"review_fault": True, "parts": (part(),)}) == [UNKNOWN] * 4


def test_a_review_fault_with_no_parts_is_still_unknown() -> None:
    assert _all({"review_fault": True}) == [UNKNOWN] * 4


def test_an_unreadable_review_is_unknown_throughout() -> None:
    assert _all({"review_unreadable": True}) == [UNKNOWN] * 4


def test_an_unknown_verdict_is_unknown_throughout() -> None:
    parts = (part(ReviewVerdict.UNKNOWN, VerdictStanding.UNPARSED),)
    assert _all({"parts": parts}) == [UNKNOWN] * 4


@pytest.mark.parametrize(
    ("verdict", "expected"),
    [
        (ReviewVerdict.PASS, "pass"),
        (ReviewVerdict.CONCERNS, "concerns"),
        (ReviewVerdict.FAIL, "fail"),
    ],
)
def test_a_single_verdict_is_lower_cased(verdict: ReviewVerdict, expected: str) -> None:
    evidence = completed_evidence(parts=(part(verdict),))
    assert value(evidence, RoutingInput.VERDICT) == expected


@pytest.mark.parametrize("standing", list(VerdictStanding))
def test_each_standing_reduces_to_itself(standing: VerdictStanding) -> None:
    evidence = completed_evidence(parts=(part(standing=standing),))
    assert value(evidence, RoutingInput.STANDING) == standing.value


def test_split_review_takes_worst_verdict() -> None:
    parts = (
        part(ReviewVerdict.PASS),
        part(ReviewVerdict.FAIL),
        part(ReviewVerdict.CONCERNS),
    )
    assert value(completed_evidence(parts=parts), RoutingInput.VERDICT) == "fail"


def test_split_review_concerns_beat_pass() -> None:
    parts = (part(ReviewVerdict.PASS), part(ReviewVerdict.CONCERNS))
    assert value(completed_evidence(parts=parts), RoutingInput.VERDICT) == "concerns"


def test_split_review_with_matching_standings_keeps_it() -> None:
    parts = (part(standing=VerdictStanding.DERIVED),) * 2
    evidence = completed_evidence(parts=parts)
    assert value(evidence, RoutingInput.STANDING) == "derived"


def test_split_review_with_differing_standings_is_unknown() -> None:
    parts = (
        part(standing=VerdictStanding.STATED),
        part(standing=VerdictStanding.DERIVED),
    )
    assert value(completed_evidence(parts=parts), RoutingInput.STANDING) == UNKNOWN


def test_split_review_takes_highest_severity() -> None:
    parts = (
        part(severity=FindingSeverity.NOTE),
        part(severity=FindingSeverity.CONCERN),
        part(severity=FindingSeverity.PASS),
    )
    assert value(completed_evidence(parts=parts), RoutingInput.SEVERITY) == "concern"


def _recurrence(*parts_: object) -> str:
    evidence = completed_evidence(parts=tuple(parts_))
    return value(evidence, RoutingInput.RECURRENCE)


def test_a_recurring_concern_recurs() -> None:
    changes = (FindingChange.NEW, FindingChange.RECURRING)
    assert _recurrence(part(changes=changes)) == "recurring"


def test_only_new_concerns_are_new() -> None:
    assert _recurrence(part(changes=(FindingChange.NEW,) * 2)) == "new"


def test_only_notes_are_clear() -> None:
    # Notes never reach routed_changes, so a review of notes has no routed findings.
    assert _recurrence(part(severity=FindingSeverity.NOTE)) == "clear"


def test_only_gone_findings_are_clear() -> None:
    # Gone findings are the previous round's; the current review has none routed.
    assert _recurrence(part(changes=())) == "clear"


def test_recurring_note_does_not_recur() -> None:
    # A recurring note is excluded when the part is built, leaving no routed change.
    assert _recurrence(part(severity=FindingSeverity.NOTE, changes=())) != "recurring"


def test_a_part_that_is_not_comparable_makes_recurrence_unknown() -> None:
    parts = (part(changes=(FindingChange.NEW,)), part(comparable=False))
    assert _recurrence(*parts) == UNKNOWN


def test_recurrence_across_split_parts_finds_the_recurring_one() -> None:
    parts = (
        part(changes=(FindingChange.NEW,)),
        part(changes=(FindingChange.RECURRING,)),
    )
    assert _recurrence(*parts) == "recurring"
