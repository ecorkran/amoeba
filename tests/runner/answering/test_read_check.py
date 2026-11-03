"""``read_check`` returns a typed verdict or a named problem, never raises (D6)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from amoeba.runner.answering.artifacts import (
    ArtifactProblem,
    CheckReply,
    ProblemKind,
    Verdict,
    read_check,
)
from amoeba.runner.answering.pipeline_file import CHECK_REPLY_FILE

FIXTURES = Path(__file__).parents[2] / "fixtures" / "answering"


def _write(directory: Path, content: object) -> None:
    text = content if isinstance(content, str) else json.dumps(content)
    (directory / CHECK_REPLY_FILE).write_text(text, encoding="utf-8")


def test_fixture_in_production_shape(tmp_path: Path) -> None:
    (tmp_path / CHECK_REPLY_FILE).write_bytes((FIXTURES / "check.json").read_bytes())
    assert read_check(tmp_path) == CheckReply(
        verdict=Verdict.YES,
        reason=(
            "The proposed answer matches and is supported by passage P1, which "
            "specifies the required commit message form. No later or contradictory "
            "passage applies."
        ),
    )


def test_no_verdict(tmp_path: Path) -> None:
    _write(tmp_path, {"verdict": "no", "reason": "contradicted"})
    assert read_check(tmp_path) == CheckReply(verdict=Verdict.NO, reason="contradicted")


def test_verdict_is_trimmed_and_case_insensitive(tmp_path: Path) -> None:
    _write(tmp_path, {"verdict": " Yes "})
    assert read_check(tmp_path) == CheckReply(verdict=Verdict.YES, reason=None)


def test_extra_keys_are_ignored(tmp_path: Path) -> None:
    _write(tmp_path, {"verdict": "no", "reason": "r", "extra": True})
    assert read_check(tmp_path) == CheckReply(verdict=Verdict.NO, reason="r")


@pytest.mark.parametrize(
    "content",
    [
        {"reason": "no verdict key"},
        {"verdict": "maybe"},
        {"verdict": None},
        ["yes"],
        "oops",
    ],
)
def test_malformed_is_never_a_no(tmp_path: Path, content: object) -> None:
    _write(tmp_path, content)
    result = read_check(tmp_path)
    assert isinstance(result, ArtifactProblem)
    assert result.kind is ProblemKind.MALFORMED


def test_missing_file(tmp_path: Path) -> None:
    result = read_check(tmp_path)
    assert isinstance(result, ArtifactProblem)
    assert result.kind is ProblemKind.MISSING


@pytest.mark.parametrize("reason", [123, ["x"]])
def test_non_string_reason_is_malformed(tmp_path: Path, reason: object) -> None:
    _write(tmp_path, {"verdict": "no", "reason": reason})
    result = read_check(tmp_path)
    assert isinstance(result, ArtifactProblem)
    assert result.kind is ProblemKind.MALFORMED
