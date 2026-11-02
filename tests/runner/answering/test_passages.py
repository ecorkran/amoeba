"""Passages (slice 143): cutting, selection, assembly, rendering, citations."""

from __future__ import annotations

from pathlib import Path

import pytest

from amoeba.runner.answering import passages
from amoeba.runner.answering.passages import cut_passages
from runner.purity import io_use

SOURCES = Path(__file__).parent / "fixtures" / "sources"


@pytest.mark.parametrize("fence", ["```", "~~~", "````"])
def test_a_heading_inside_a_code_fence_does_not_cut(fence: str) -> None:
    text = f"# Top\n{fence}\n# not a heading\n{fence}\nafter\n"

    assert cut_passages(text) == (text,)


def test_a_shorter_or_different_fence_does_not_close_a_fence() -> None:
    text = "# Top\n````\n```\n# inside\n~~~~\n````\n## Next\n"

    assert cut_passages(text) == (
        "# Top\n````\n```\n# inside\n~~~~\n````\n",
        "## Next\n",
    )


def test_a_level_four_heading_does_not_cut() -> None:
    text = "# Top\ntext\n#### Deep\nmore\n"

    assert cut_passages(text) == (text,)


def test_headings_of_levels_one_to_three_cut() -> None:
    text = "# One\na\n## Two\nb\n### Three\nc\n"

    assert cut_passages(text) == ("# One\na\n", "## Two\nb\n", "### Three\nc\n")


def test_front_matter_is_its_own_passage() -> None:
    text = "---\ndocType: x\n---\n\n# Title\nbody\n"

    assert cut_passages(text) == ("---\ndocType: x\n---\n\n", "# Title\nbody\n")


def test_a_file_without_headings_is_one_passage() -> None:
    assert cut_passages("plain\nrules\n") == ("plain\nrules\n",)


def test_an_empty_file_gives_no_passages() -> None:
    assert cut_passages("") == ()


def test_a_blank_preamble_is_dropped() -> None:
    assert cut_passages("\n  \n# Title\nbody\n") == ("# Title\nbody\n",)


@pytest.mark.parametrize(
    ("heading", "cuts"),
    [("   # Indented", True), ("    # Code block", False), ("#tag", False)],
)
def test_leading_spaces_and_a_missing_space_decide_whether_a_line_is_a_heading(
    heading: str, cuts: bool
) -> None:
    text = f"# Top\n{heading}\n"

    assert (len(cut_passages(text)) == 2) is cuts


def test_a_bare_hash_line_is_a_heading() -> None:
    assert cut_passages("# Top\n#\nx\n") == ("# Top\n", "#\nx\n")


def test_a_final_line_without_a_newline_is_kept() -> None:
    assert cut_passages("# A\n# B") == ("# A\n", "# B")


def test_crlf_text_survives_cutting() -> None:
    text = "# A\r\nbody\r\n## B\r\nmore\r\n"

    assert cut_passages(text) == ("# A\r\nbody\r\n", "## B\r\nmore\r\n")


def _fixture_files() -> list[Path]:
    return sorted(path for path in SOURCES.rglob("*") if path.is_file())


def test_the_fixture_directory_holds_the_frozen_files() -> None:
    assert len(_fixture_files()) == 9


@pytest.mark.parametrize("path", _fixture_files(), ids=lambda path: path.name)
def test_passages_of_a_real_file_join_back_to_it(path: Path) -> None:
    text = path.read_text()

    pieces = cut_passages(text)

    assert "".join(pieces) == text
    for piece in pieces[1:]:
        assert piece.lstrip(" ").startswith("#")


def test_the_passages_module_does_no_io() -> None:
    assert io_use(passages) == []
