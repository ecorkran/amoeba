"""Passage provenance and the scratch-directory helpers a launch uses."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from amoeba.answering.inputs import QuestionInput
from amoeba.answering.launch import (
    discard_scratch,
    passage_refs,
    prepare_scratch_directory,
)
from amoeba.answering.passages import Passage, PassageKind, PassageSet
from amoeba.answering.values import PassageRef

DATE = datetime(2026, 11, 8, tzinfo=UTC)
QUESTION = QuestionInput("221 the-cut", "Which base branch?")


def _passage(
    passage_id: str,
    kind: PassageKind,
    source: str | None,
    question_id: str | None = None,
) -> Passage:
    return Passage(
        passage_id, kind, source, DATE, "text", None, None, question_id, None
    )


def _set(*passages: Passage) -> PassageSet:
    return PassageSet(passages, "c0ffee", ())


def test_a_file_passage_is_referenced_by_its_path() -> None:
    refs = passage_refs(_set(_passage("P1", PassageKind.RULE, "CLAUDE.md")))

    assert refs == (PassageRef("P1", "CLAUDE.md", None, DATE),)


def test_a_pm_passage_is_referenced_by_its_record_id() -> None:
    refs = passage_refs(_set(_passage("P2", PassageKind.PM_ANSWER, None, "q-7")))

    assert refs == (PassageRef("P2", "q-7", "q-7", DATE),)


def test_a_passage_with_no_source_is_a_programming_error() -> None:
    with pytest.raises(ValueError, match="P3"):
        passage_refs(_set(_passage("P3", PassageKind.PM_ANSWER, None)))


def test_the_scratch_directory_is_made_and_filled(tmp_path: Path) -> None:
    scratch = tmp_path / "answering" / "run-1"

    problem = prepare_scratch_directory(scratch, QUESTION, "## P1\n", 0.5)

    assert problem is None
    assert (scratch / "question.md").is_file()
    assert (scratch / "passages.md").is_file()


def test_an_existing_scratch_directory_is_never_reused(tmp_path: Path) -> None:
    scratch = tmp_path / "run-1"
    scratch.mkdir()

    problem = prepare_scratch_directory(scratch, QUESTION, "## P1\n", 0.5)

    assert problem is not None and "FileExistsError" in problem
    assert list(scratch.iterdir()) == []


def test_discarding_removes_the_directory_and_tolerates_a_missing_one(
    tmp_path: Path,
) -> None:
    scratch = tmp_path / "run-1"
    prepare_scratch_directory(scratch, QUESTION, "## P1\n", 0.5)

    discard_scratch(scratch)
    discard_scratch(scratch)

    assert not scratch.exists()
