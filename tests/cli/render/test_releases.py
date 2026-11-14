"""The text of ``report-release`` and ``changes``, exact (slice 227, D5)."""

from __future__ import annotations

import pytest

from amoeba.cli.render.releases import render_changes, render_report_release
from amoeba.cli.render.text import COLUMNS
from amoeba.operations.changes_models import (
    ChangesOutcome,
    ChangesResult,
    ChangesWarning,
    ChangesWarningCode,
    MemberRef,
    ProviderPair,
)
from amoeba.operations.reject_codes import RejectCode
from amoeba.operations.report_release_models import (
    ReleaseProblem,
    ReleaseReport,
    ReportOutcome,
    ReportReleaseResult,
)
from amoeba.store.vocabulary import ConsumedMode

COMMIT = "a" * 40
SINCE = "2026-11-09T12:00:00+00:00"


def _report(
    *, version: str | None = None, changed: str = "what changed"
) -> ReleaseReport:
    return ReleaseReport(
        seq=1,
        commit=COMMIT,
        version=version,
        changed=changed,
        touched=("cli", "store"),
        reported_at=SINCE,
        versioned_at=None if version is None else SINCE,
    )


def _result(
    outcome: ReportOutcome, report: ReleaseReport | None = None
) -> ReportReleaseResult:
    return ReportReleaseResult(
        outcome=outcome, member="member", report=report, problems=()
    )


def test_recorded_and_versioned_both_say_reported() -> None:
    for outcome in (ReportOutcome.RECORDED, ReportOutcome.VERSIONED):
        text = render_report_release(_result(outcome, _report()))
        assert text.splitlines()[0] == "reported"


def test_the_other_outcomes_say_their_own_word() -> None:
    for outcome in (
        ReportOutcome.UNCHANGED,
        ReportOutcome.CORRECTED,
        ReportOutcome.WITHDRAWN,
    ):
        assert render_report_release(_result(outcome)).splitlines() == [outcome.value]


def test_a_report_shows_the_commit_and_version_after_the_first_line() -> None:
    text = render_report_release(
        _result(ReportOutcome.RECORDED, _report(version="tag-one"))
    )
    assert text.splitlines() == ["reported", f"  {COMMIT} · tag-one"]


def test_a_rejection_prints_its_code_and_each_detail() -> None:
    result = ReportReleaseResult(
        outcome=ReportOutcome.REJECTED,
        member=None,
        report=None,
        problems=(
            ReleaseProblem(code=RejectCode.MALFORMED, detail="commit: too short"),
            ReleaseProblem(code=RejectCode.MALFORMED, detail="touched: missing"),
        ),
    )
    assert render_report_release(result).splitlines() == [
        "rejected: malformed",
        "  commit: too short",
        "  touched: missing",
    ]


def _pair(name: str | None, *reports: ReleaseReport) -> ProviderPair:
    return ProviderPair(
        provider=MemberRef(id=f"{name or 'unnamed'}-id", name=name),
        consumed=ConsumedMode.FROM_SOURCE,
        releases=reports,
    )


def _changes(
    *pairs: ProviderPair, warnings: tuple[ChangesWarning, ...] = ()
) -> ChangesResult:
    return ChangesResult(
        outcome=ChangesOutcome.LISTED,
        member=MemberRef(id="me", name="me"),
        since=SINCE,
        pairs=pairs,
        problems=(),
        warnings=warnings,
    )


def test_changes_prints_one_entry_per_report_and_cuts_long_text() -> None:
    long_text = "word " * 60
    text = render_changes(
        _changes(
            _pair("core", _report(version="tag-one", changed=long_text)),
            _pair("lint"),
        )
    )
    lines = text.splitlines()
    assert lines[0] == f"core · {COMMIT} · tag-one"
    assert lines[1].startswith("  changed: word word")
    assert lines[1].endswith("…")
    assert len(lines[1]) <= COLUMNS
    assert lines[2] == "  touched: cli, store"
    assert len(lines) == 3
    assert "No changes since" not in text


def test_an_unnamed_provider_is_shown_by_id_without_a_version() -> None:
    text = render_changes(_changes(_pair(None, _report())))
    assert text.splitlines()[0] == f"unnamed-id · {COMMIT}"


def test_no_changes_is_said_only_when_every_pair_is_empty() -> None:
    empty = render_changes(_changes(_pair("core"), _pair("lint")))
    assert empty == f"No changes since {SINCE}.\n"
    assert render_changes(_changes()) == f"No changes since {SINCE}.\n"
    assert "No changes since" not in render_changes(_changes(_pair("core", _report())))


def test_a_warning_is_printed() -> None:
    warning = ChangesWarning(
        code=ChangesWarningCode.NOT_IN_CONTEXT_FORGE, detail="no name for some-id"
    )
    text = render_changes(_changes(_pair(None, _report()), warnings=(warning,)))
    assert text.splitlines()[-1] == "warning: no name for some-id"


def test_a_rejected_changes_result_prints_its_code_and_detail() -> None:
    result = ChangesResult(
        outcome=ChangesOutcome.REJECTED,
        member=None,
        since=SINCE,
        pairs=(),
        problems=(
            ReleaseProblem(code=RejectCode.NOT_A_MEMBER, detail="in no program"),
        ),
        warnings=(),
    )
    assert render_changes(result).splitlines() == [
        "rejected: not_a_member",
        "  in no program",
    ]


def test_a_rejected_result_with_no_problem_is_an_error_not_a_guess() -> None:
    result = ReportReleaseResult(
        outcome=ReportOutcome.REJECTED, member=None, report=None, problems=()
    )
    with pytest.raises(ValueError, match="at least one problem"):
        render_report_release(result)
