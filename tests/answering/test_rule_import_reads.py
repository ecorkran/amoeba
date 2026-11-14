"""Following ``@path`` imports against real git repos (slice 229, D10)."""

from __future__ import annotations

from pathlib import Path

from amoeba.answering.import_follow import IMPORT_DEPTH
from amoeba.answering.passages import SourcesProblemKind
from amoeba.answering.source_reads import CommittedSources
from answering.rules_reads_support import (
    build_repo,
    default_choice,
    named_choice,
    problem_of,
    read,
    read_paths,
)
from answering.sources_repo import CountingRun


def _chain(length: int) -> dict[str, str]:
    """``CLAUDE.md`` importing ``docs/f1.md``, which imports on, ``length`` deep."""
    files = {"CLAUDE.md": "# Rules\n@docs/f1.md\n"}
    for number in range(1, length + 1):
        follow = f"@f{number + 1}.md\n" if number < length else ""
        files[f"docs/f{number}.md"] = f"# File {number}\n{follow}"
    return files


def test_the_depth_limit_is_three() -> None:
    assert IMPORT_DEPTH == 3


def test_a_chain_of_depth_three_is_read_each_file_after_its_importer(
    tmp_path: Path,
) -> None:
    repo = build_repo(tmp_path / "r", _chain(3))

    assert read_paths(read(repo, default_choice("CLAUDE.md"))) == [
        "CLAUDE.md",
        "docs/f1.md",
        "docs/f2.md",
        "docs/f3.md",
    ]


def test_a_chain_of_depth_four_declines_naming_the_chain(tmp_path: Path) -> None:
    repo = build_repo(tmp_path / "r", _chain(4))

    problem = problem_of(
        read(repo, default_choice("CLAUDE.md")), SourcesProblemKind.UNREADABLE
    )

    assert problem.detail == (
        "imports are more than 3 deep: "
        "CLAUDE.md -> docs/f1.md -> docs/f2.md -> docs/f3.md -> docs/f4.md"
    )


def test_a_cycle_reads_each_file_once(tmp_path: Path) -> None:
    repo = build_repo(
        tmp_path / "r",
        {"CLAUDE.md": "# One\n@two.md\n", "two.md": "# Two\n@CLAUDE.md and @two.md\n"},
    )

    assert read_paths(read(repo, named_choice("CLAUDE.md"))) == ["CLAUDE.md", "two.md"]


def test_an_import_resolves_against_the_importing_files_directory(
    tmp_path: Path,
) -> None:
    repo = build_repo(
        tmp_path / "r",
        {
            "docs/a.md": "# A\n@b.md and @../top.md\n",
            "docs/b.md": "# B\n",
            "top.md": "# T\n",
        },
    )

    assert read_paths(read(repo, named_choice("docs/a.md"))) == [
        "docs/a.md",
        "docs/b.md",
        "top.md",
    ]


def test_an_import_is_placed_directly_after_its_importer(tmp_path: Path) -> None:
    repo = build_repo(
        tmp_path / "r",
        {"A.md": "# A\n@c.md\n", "B.md": "# B\n", "c.md": "# C\n"},
    )

    assert read_paths(read(repo, named_choice("A.md", "B.md"))) == [
        "A.md",
        "c.md",
        "B.md",
    ]


def test_an_import_of_a_later_entry_is_read_once_at_the_import(tmp_path: Path) -> None:
    repo = build_repo(
        tmp_path / "r", {"A.md": "# A\n@B.md\n", "B.md": "# B\n", "C.md": "# C\n"}
    )

    paths = read_paths(read(repo, named_choice("A.md", "B.md", "C.md")))

    assert paths == ["A.md", "B.md", "C.md"]


def test_a_missing_import_under_a_default_entry_is_skipped(tmp_path: Path) -> None:
    repo = build_repo(
        tmp_path / "r", {"CLAUDE.md": "# Rules\n@gone.md and @nowhere/x.md\n"}
    )

    assert read_paths(read(repo, default_choice("CLAUDE.md"))) == ["CLAUDE.md"]


def test_a_missing_import_under_a_named_entry_is_sources_missing(
    tmp_path: Path,
) -> None:
    repo = build_repo(tmp_path / "r", {"CLAUDE.md": "# Rules\n@gone.md\n"})

    problem = problem_of(
        read(repo, named_choice("CLAUDE.md")), SourcesProblemKind.MISSING
    )

    assert problem.detail == "import @gone.md in CLAUDE.md matches no file"


def test_a_missing_import_in_a_missing_directory_under_a_named_entry_is_missing(
    tmp_path: Path,
) -> None:
    repo = build_repo(tmp_path / "r", {"CLAUDE.md": "# Rules\n@nowhere/x.md\n"})

    problem = problem_of(
        read(repo, named_choice("CLAUDE.md")), SourcesProblemKind.MISSING
    )

    assert problem.detail == "import @nowhere/x.md in CLAUDE.md matches no file"


def test_an_import_outside_the_repository_declines_under_a_default_entry(
    tmp_path: Path,
) -> None:
    repo = build_repo(tmp_path / "r", {"docs/a.md": "# A\n@../../outside.md\n"})

    problem = problem_of(
        read(repo, default_choice("docs/a.md")), SourcesProblemKind.UNREADABLE
    )

    assert problem.detail == (
        "import @../../outside.md in docs/a.md resolves outside the repository"
    )


def test_an_import_outside_the_repository_declines_under_a_named_entry(
    tmp_path: Path,
) -> None:
    repo = build_repo(tmp_path / "r", {"CLAUDE.md": "# A\n@../outside.md\n"})

    problem = problem_of(
        read(repo, named_choice("CLAUDE.md")), SourcesProblemKind.UNREADABLE
    )

    assert problem.detail == (
        "import @../outside.md in CLAUDE.md resolves outside the repository"
    )


def test_imported_text_counts_against_the_size_cap(tmp_path: Path) -> None:
    importer = "# Rules\n@big.md\n"
    imported = "# Big\n" + "x" * 500 + "\n"
    repo = build_repo(tmp_path / "r", {"CLAUDE.md": importer, "big.md": imported})
    together = len(importer) + len(imported)

    fits = read(repo, named_choice("CLAUDE.md"), max_chars=together)
    too_big = read(repo, named_choice("CLAUDE.md"), max_chars=together - 1)

    assert isinstance(fits, CommittedSources)
    assert fits.chars == together
    assert len(importer) < together - 1  # the importer alone would have fit
    problem = problem_of(too_big, SourcesProblemKind.TOO_LARGE)
    assert f"the limit is {together - 1}" in problem.detail


def test_an_imported_section_equal_to_an_earlier_rule_section_is_dropped(
    tmp_path: Path,
) -> None:
    shared = "## Shared\n" + "same words\n" * 20
    repo = build_repo(
        tmp_path / "r",
        {"CLAUDE.md": f"# Rules\n@more.md\n{shared}", "more.md": f"# More\n{shared}"},
    )

    result = read(repo, named_choice("CLAUDE.md"))

    assert isinstance(result, CommittedSources)
    assert read_paths(result) == ["CLAUDE.md", "more.md"]
    assert result.chars == len("# Rules\n@more.md\n") + len(shared) + len("# More\n")


def test_a_non_markdown_rule_file_is_not_searched_for_imports(tmp_path: Path) -> None:
    repo = build_repo(tmp_path / "r", {"rules.txt": "@other.md\n", "other.md": "# O\n"})

    assert read_paths(read(repo, named_choice("rules.txt"))) == ["rules.txt"]


def test_an_import_in_an_already_listed_directory_makes_no_new_listing_call(
    tmp_path: Path,
) -> None:
    repo = build_repo(
        tmp_path / "r", {"docs/a.md": "# A\n@b.md\n", "docs/b.md": "# B\n"}
    )
    counting = CountingRun()

    result = read(repo, named_choice("docs/a.md"), run=counting)

    assert read_paths(result) == ["docs/a.md", "docs/b.md"]
    # resolve, ls-tree docs, show docs, then log + show for each of the two files.
    assert counting.asked == 1 + 1 + 1 + 2 * 2
