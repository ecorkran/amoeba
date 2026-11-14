"""The text of ``report-release`` and ``changes`` (slice 227, D5).

``report-release`` opens with one word: ``reported`` (a new report or a version added),
``unchanged``, ``corrected``, ``withdrawn``, or ``rejected: <code>`` and a line per
problem. ``changes`` prints one entry per visible report. Prose is cut to the width and
the full text is in ``-j``.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import assert_never

from amoeba.cli.render.text import SEPARATOR, indented, prose_line
from amoeba.operations.changes_models import (
    ChangesOutcome,
    ChangesResult,
    ProviderPair,
)
from amoeba.operations.report_release_models import (
    ReleaseProblem,
    ReleaseReport,
    ReportOutcome,
    ReportReleaseResult,
)

_REPORTED = "reported"


def _rejected(problems: Sequence[ReleaseProblem]) -> str:
    if not problems:
        raise ValueError("a rejected result carries at least one problem")
    lines = [f"rejected: {problems[0].code.value}"]
    lines.extend(prose_line(indented(""), problem.detail) for problem in problems)
    return "\n".join(lines) + "\n"


def _report_lines(report: ReleaseReport) -> list[str]:
    return [
        prose_line(indented("changed: "), report.changed),
        prose_line(indented("touched: "), ", ".join(report.touched)),
    ]


def render_report_release(result: ReportReleaseResult) -> str:
    match result.outcome:
        case ReportOutcome.REJECTED:
            return _rejected(result.problems)
        case ReportOutcome.RECORDED | ReportOutcome.VERSIONED:
            first = _REPORTED
        case (
            ReportOutcome.UNCHANGED | ReportOutcome.CORRECTED | ReportOutcome.WITHDRAWN
        ):
            first = result.outcome.value
        case _:
            assert_never(result.outcome)
    lines = [first]
    if result.report is not None:
        version = result.report.version
        head = SEPARATOR.join(
            (result.report.commit, *(() if version is None else (version,)))
        )
        lines.append(indented(head))
    return "\n".join(lines) + "\n"


def _provider_label(pair: ProviderPair) -> str:
    return pair.provider.name or pair.provider.id


def _entry(pair: ProviderPair, report: ReleaseReport) -> list[str]:
    parts = [_provider_label(pair), report.commit]
    if report.version is not None:
        parts.append(report.version)
    return [SEPARATOR.join(parts), *_report_lines(report)]


def render_changes(result: ChangesResult) -> str:
    if result.outcome is ChangesOutcome.REJECTED:
        return _rejected(result.problems)
    lines: list[str] = []
    for pair in result.pairs:
        for report in pair.releases:
            lines.extend(_entry(pair, report))
    if not lines:
        lines.append(f"No changes since {result.since}.")
    lines.extend(prose_line("warning: ", warning.detail) for warning in result.warnings)
    return "\n".join(lines) + "\n"
