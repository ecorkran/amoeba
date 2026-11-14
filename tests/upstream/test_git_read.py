"""`git_read` only reads: an allowlist, bounded calls, and tree-listing parsers."""

from __future__ import annotations

import subprocess
from datetime import datetime
from functools import partial
from pathlib import Path
from typing import Any

import pytest
from git_repo import commit_file, head_of, make_repo

from amoeba.upstream.git_read import (
    GIT_SUBCOMMANDS,
    GitReadFailure,
    GitReadResult,
    git_read,
    last_change_args,
    ls_tree_args,
    parse_tree_directories,
    parse_tree_listing,
    resolve_commit_args,
    show_object_args,
)

TIMEOUT = 8.0


@pytest.mark.parametrize("subcommand", ["commit", "checkout", "push", "merge"])
def test_a_subcommand_outside_the_allowlist_is_refused(
    subcommand: str, tmp_path: Path
) -> None:
    assert subcommand not in GIT_SUBCOMMANDS

    with pytest.raises(ValueError, match=subcommand):
        git_read((subcommand,), tmp_path, subprocess.run, TIMEOUT)


def test_an_option_cannot_smuggle_a_second_subcommand_past_the_allowlist(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="push"):
        git_read(("--no-pager", "push"), tmp_path, subprocess.run, TIMEOUT)


def test_git_runs_without_a_prompt_and_with_stdin_closed(tmp_path: Path) -> None:
    seen: dict[str, Any] = {}

    def run(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        seen.update(kwargs, argv=argv)
        return subprocess.CompletedProcess(argv, 0, "", "")

    git_read(resolve_commit_args("main"), tmp_path, run, TIMEOUT)

    assert seen["env"]["GIT_TERMINAL_PROMPT"] == "0"
    assert seen["stdin"] == subprocess.DEVNULL
    assert seen["cwd"] == tmp_path
    assert seen["timeout"] == TIMEOUT
    assert seen["argv"][0] == "git"


@pytest.mark.parametrize(
    "error",
    [subprocess.TimeoutExpired("git", TIMEOUT), FileNotFoundError("git")],
)
def test_a_timeout_and_a_missing_executable_are_failures_not_exceptions(
    error: Exception, tmp_path: Path
) -> None:
    def run(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        raise error

    result = git_read(resolve_commit_args("main"), tmp_path, run, TIMEOUT)

    assert isinstance(result, GitReadFailure)
    assert "log" in result.detail


# Slice 143, D2: show and log read objects at a pinned commit.


def test_the_allowlist_holds_the_two_read_commands() -> None:
    assert GIT_SUBCOMMANDS == {"show", "log", "ls-tree"}


def test_the_object_read_builders_give_exact_arguments() -> None:
    assert resolve_commit_args("main") == ("log", "-1", "--format=%H", "main")
    assert show_object_args("abc123", "docs/a.md") == ("show", "abc123:docs/a.md")
    assert show_object_args("abc123", "") == ("show", "abc123:")
    assert last_change_args("abc123", "docs/a.md") == (
        "log",
        "-1",
        "--format=%cI",
        "abc123",
        "--",
        "docs/a.md",
    )


def test_a_commit_or_target_that_looks_like_an_option_is_refused() -> None:
    option = "--output=x"
    for build in (
        resolve_commit_args,
        partial(show_object_args, path="a.md"),
        partial(last_change_args, path="a.md"),
        partial(ls_tree_args, directory="docs"),
    ):
        with pytest.raises(ValueError, match="--output"):
            build(option)


def _object_repo(tmp_path: Path) -> Path:
    repo = make_repo(tmp_path / "repo")
    commit_file(repo, "docs/top.md", "top\n", "top")
    commit_file(repo, "docs/nested/deep.md", "deep\n", "deep")
    return repo


def test_ls_tree_args_end_the_options_before_the_directory() -> None:
    assert ls_tree_args("abc123", "-docs") == (
        "ls-tree",
        "--name-only",
        "abc123",
        "--",
        "-docs/",
    )


def test_ls_tree_says_a_directory_is_absent_with_exit_zero_and_no_output(
    tmp_path: Path,
) -> None:
    repo = _object_repo(tmp_path)
    commit = head_of(repo)

    present = _read(repo, ls_tree_args(commit, "docs"))
    absent = _read(repo, ls_tree_args(commit, "nowhere"))

    assert (present.exit_code, present.stdout.split()) == (
        0,
        ["docs/nested", "docs/top.md"],
    )
    assert (absent.exit_code, absent.stdout) == (0, "")


def _read(repo: Path, args: tuple[str, ...]) -> GitReadResult:
    result = git_read(args, repo, subprocess.run, TIMEOUT)
    assert isinstance(result, GitReadResult)
    return result


def test_a_directory_listing_keeps_files_and_drops_subdirectories(
    tmp_path: Path,
) -> None:
    repo = _object_repo(tmp_path)
    commit = head_of(repo)

    listing = _read(repo, show_object_args(commit, "docs")).stdout

    assert listing.startswith("tree ")
    assert parse_tree_listing(listing) == ("top.md",)


def test_a_directory_listing_names_its_subdirectories_without_the_slash(
    tmp_path: Path,
) -> None:
    repo = _object_repo(tmp_path)
    commit = head_of(repo)

    listing = _read(repo, show_object_args(commit, "docs")).stdout

    assert parse_tree_directories(listing) == ("nested",)


def test_the_root_listing_names_root_level_files(tmp_path: Path) -> None:
    repo = _object_repo(tmp_path)
    commit = head_of(repo)

    listing = _read(repo, show_object_args(commit, "")).stdout

    assert parse_tree_listing(listing) == ("README.md",)


def test_a_file_named_like_the_tree_header_is_still_listed() -> None:
    text = "tree abc:docs\n\ntree notes.md\nother.md\n"

    assert parse_tree_listing(text) == ("tree notes.md", "other.md")


def test_the_listing_parser_tolerates_crlf_and_trailing_blanks() -> None:
    text = "tree abc:docs\r\n\r\na.md  \r\nsub/\r\nb.md\r\n\r\n"

    assert parse_tree_listing(text) == ("a.md", "b.md")


def test_show_prints_a_blob_and_log_prints_one_date_and_the_commit(
    tmp_path: Path,
) -> None:
    repo = _object_repo(tmp_path)
    commit = head_of(repo)

    blob = _read(repo, show_object_args(commit, "docs/top.md"))
    resolved = _read(repo, resolve_commit_args("main"))
    changed = _read(repo, last_change_args(commit, "docs/top.md"))

    assert blob.stdout == "top\n"
    assert resolved.stdout.strip() == commit
    assert len(changed.stdout.strip().splitlines()) == 1
    assert datetime.fromisoformat(changed.stdout.strip()).tzinfo is not None
