"""The provider-failure rule: pure behavior, and its single definition in src/."""

from __future__ import annotations

import ast
from pathlib import Path

from amoeba.store.evidence_models import ReviewVerdict, provider_failure_problem

SRC = Path(__file__).parents[2] / "src" / "amoeba"
EVIDENCE_MODELS = SRC / "store" / "evidence_models.py"


def _problem(verdict: ReviewVerdict, findings: list[object], failed: bool = True):
    return provider_failure_problem(
        provider_failure=failed, verdict=verdict, findings=findings
    )


def test_a_non_failure_has_no_problem() -> None:
    assert _problem(ReviewVerdict.PASS, [object()], failed=False) is None


def test_a_failure_with_unknown_and_no_findings_is_acceptable() -> None:
    assert _problem(ReviewVerdict.UNKNOWN, []) is None


def test_a_failure_with_another_verdict_names_the_verdict() -> None:
    reason = _problem(ReviewVerdict.CONCERNS, [])
    assert reason is not None
    assert ReviewVerdict.CONCERNS.value in reason


def test_a_failure_with_findings_is_rejected() -> None:
    reason = _problem(ReviewVerdict.UNKNOWN, [object()])
    assert reason is not None
    assert "findings" in reason


def _string_constant_files(text: str) -> list[Path]:
    """Source files under ``src/amoeba`` holding a string constant containing text."""
    holders: list[Path] = []
    for path in sorted(SRC.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        if any(
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and text in node.value
            for node in ast.walk(tree)
        ):
            holders.append(path)
    return holders


def test_each_reason_text_is_defined_in_exactly_one_place() -> None:
    # Fragments come from calling the function, so the test retypes nothing.
    verdict_reason = _problem(ReviewVerdict.CONCERNS, [])
    findings_reason = _problem(ReviewVerdict.UNKNOWN, [object()])
    assert verdict_reason is not None and findings_reason is not None
    # The verdict reason is an f-string, so check its constant prefix.
    verdict_prefix = verdict_reason.split(ReviewVerdict.UNKNOWN.value)[0]
    for fragment in (verdict_prefix, findings_reason):
        assert _string_constant_files(fragment) == [EVIDENCE_MODELS], fragment
