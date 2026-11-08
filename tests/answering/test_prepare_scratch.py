"""``prepare_scratch`` writes exactly the four entries of slice 140 D7."""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from amoeba.answering.inputs import (
    QuestionInput,
    prepare_scratch,
    render_squadron_config,
)

QUESTION = QuestionInput("140 answering-pipeline", "Which base branch?")
PASSAGES = "## Passage P1\n\nkind: rule\n\nCafé rule text — verbatim.\n"


def test_writes_the_four_entries(tmp_path: Path) -> None:
    prepare_scratch(tmp_path, QUESTION, PASSAGES, 1.5)
    assert sorted(entry.name for entry in tmp_path.iterdir()) == [
        ".squadron.toml",
        "passages.md",
        "question.md",
        "rules",
    ]
    assert list((tmp_path / "rules").iterdir()) == []
    assert (
        (tmp_path / "question.md")
        .read_text(encoding="utf-8")
        .endswith("Which base branch?")
    )


def test_passages_are_written_byte_for_byte(tmp_path: Path) -> None:
    prepare_scratch(tmp_path, QUESTION, PASSAGES, 1.5)
    assert (tmp_path / "passages.md").read_bytes() == PASSAGES.encode("utf-8")


def test_squadron_config_holds_cap_and_absolute_rules_dir(tmp_path: Path) -> None:
    prepare_scratch(tmp_path, QUESTION, PASSAGES, 1.5)
    config = tomllib.loads((tmp_path / ".squadron.toml").read_text(encoding="utf-8"))
    assert config["pipeline.max_cost_usd"] == 1.5
    rules_dir = Path(config["rules_dir"])
    assert rules_dir.is_absolute()
    assert rules_dir == tmp_path.resolve() / "rules"


def _listing(directory: Path) -> list[str]:
    return sorted(entry.name for entry in directory.iterdir())


def test_missing_directory_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="does not exist"):
        prepare_scratch(tmp_path / "absent", QUESTION, PASSAGES, 1.0)


def test_non_empty_directory_is_refused_and_unchanged(tmp_path: Path) -> None:
    (tmp_path / "keep.txt").write_text("x")
    with pytest.raises(ValueError, match="not empty"):
        prepare_scratch(tmp_path, QUESTION, PASSAGES, 1.0)
    assert _listing(tmp_path) == ["keep.txt"]


@pytest.mark.parametrize("cap", [0, -1.0, float("nan"), float("inf")])
def test_non_positive_cap_is_refused_and_unchanged(tmp_path: Path, cap: float) -> None:
    with pytest.raises(ValueError, match="max_cost_usd"):
        prepare_scratch(tmp_path, QUESTION, PASSAGES, cap)
    assert _listing(tmp_path) == []


def test_empty_passages_are_refused_and_unchanged(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="passages_markdown"):
        prepare_scratch(tmp_path, QUESTION, "", 1.0)
    assert _listing(tmp_path) == []


def test_invalid_question_is_refused_and_unchanged(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="question"):
        prepare_scratch(tmp_path, QuestionInput("140 x", ""), PASSAGES, 1.0)
    assert _listing(tmp_path) == []


@pytest.mark.parametrize("cap", [0, -1.0, float("nan"), float("inf")])
def test_render_squadron_config_refuses_a_bad_cap_itself(
    tmp_path: Path, cap: float
) -> None:
    with pytest.raises(ValueError, match="max_cost_usd"):
        render_squadron_config(tmp_path, cap)
