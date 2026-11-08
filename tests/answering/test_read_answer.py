"""``read_answer`` returns a typed reply or a named problem, never raises (D6)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from amoeba.answering.artifacts import (
    AnswererDecline,
    ArtifactProblem,
    ProblemKind,
    ProposedAnswer,
    read_answer,
)
from amoeba.answering.pipeline_file import ANSWER_REPLY_FILE

FIXTURES = Path(__file__).parents[1] / "fixtures" / "answering"


def _write(directory: Path, content: object) -> None:
    text = content if isinstance(content, str) else json.dumps(content)
    (directory / ANSWER_REPLY_FILE).write_text(text, encoding="utf-8")


def _problem(directory: Path) -> ArtifactProblem:
    result = read_answer(directory)
    assert isinstance(result, ArtifactProblem)
    return result


def test_fixture_in_production_shape(tmp_path: Path) -> None:
    (tmp_path / ANSWER_REPLY_FILE).write_bytes((FIXTURES / "answer.json").read_bytes())
    assert read_answer(tmp_path) == ProposedAnswer(
        answer=(
            "Commit messages must use the form `type: short imperative summary`, "
            "for example `fix: handle empty input`."
        ),
        cited=("P1",),
    )


def test_valid_decline(tmp_path: Path) -> None:
    _write(tmp_path, {"kind": "decline", "reason": "no passage settles it"})
    assert read_answer(tmp_path) == AnswererDecline(reason="no passage settles it")


def test_missing_file(tmp_path: Path) -> None:
    assert _problem(tmp_path).kind is ProblemKind.MISSING


@pytest.mark.parametrize(
    "content",
    [
        "not json at all",
        "",
        [{"kind": "decline", "reason": "r"}],
        {"kind": "maybe"},
        {"answer": "text", "cited": []},
        {"kind": 3},
        {"kind": "answer", "answer": "", "cited": ["P1"]},
        {"kind": "answer", "answer": "   ", "cited": ["P1"]},
        {"kind": "answer", "cited": ["P1"]},
        {"kind": "answer", "answer": "a", "cited": "P1"},
        {"kind": "answer", "answer": "a", "cited": [1]},
        {"kind": "answer", "answer": "a"},
        {"kind": "decline"},
        {"kind": "decline", "reason": ""},
    ],
)
def test_malformed(tmp_path: Path, content: object) -> None:
    _write(tmp_path, content)
    problem = _problem(tmp_path)
    assert problem.kind is ProblemKind.MALFORMED
    assert problem.detail


def test_kind_is_trimmed_and_case_insensitive(tmp_path: Path) -> None:
    _write(tmp_path, {"kind": " ANSWER ", "answer": "a", "cited": ["P1"]})
    assert read_answer(tmp_path) == ProposedAnswer(answer="a", cited=("P1",))


def test_unknown_keys_are_ignored(tmp_path: Path) -> None:
    _write(tmp_path, {"kind": "decline", "reason": "r", "extra": [1, 2]})
    assert read_answer(tmp_path) == AnswererDecline(reason="r")


def test_empty_cited_list_is_accepted(tmp_path: Path) -> None:
    _write(tmp_path, {"kind": "answer", "answer": "a", "cited": []})
    assert read_answer(tmp_path) == ProposedAnswer(answer="a", cited=())


def test_non_utf8_file_is_malformed(tmp_path: Path) -> None:
    (tmp_path / ANSWER_REPLY_FILE).write_bytes(
        b'{"kind": "decline", "reason": "\xff\xfe"}'
    )
    assert _problem(tmp_path).kind is ProblemKind.MALFORMED


def test_reply_path_that_is_a_directory_is_malformed(tmp_path: Path) -> None:
    (tmp_path / ANSWER_REPLY_FILE).mkdir()
    assert _problem(tmp_path).kind is ProblemKind.MALFORMED
