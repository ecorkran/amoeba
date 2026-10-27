"""D10: the parser reads real `git status` output, and `git_read` only reads."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from amoeba.runner.budget import TickBudget
from amoeba.runner.git_read import (
    GIT_SUBCOMMANDS,
    GitReadFailure,
    GitReadResult,
    GitStatus,
    git_read,
    is_ancestor_args,
    parse_porcelain_v2,
    status_args,
)
from runner.git_repo import (
    commit_file,
    detach_head,
    head_of,
    make_branch,
    make_repo,
    switch,
)
from runner.observe_support import Clock, Host

FIXTURES = Path(__file__).parents[1] / "fixtures" / "git"
TIMEOUT = 8.0


def _budget(deadline: float = 1_000.0) -> TickBudget:
    return TickBudget(deadline, Host(), Clock().monotonic)


def _fixture(name: str) -> str:
    return (FIXTURES / f"status_{name}.txt").read_text()


def _head_in(name: str) -> str:
    """The ``branch.oid`` the captured fixture itself carries."""
    for line in _fixture(name).splitlines():
        if line.startswith("# branch.oid "):
            return line.split()[-1]
    raise AssertionError(f"no branch.oid in the {name} fixture")


@pytest.mark.parametrize(
    ("name", "branch", "dirty"),
    [
        ("clean_main", "main", ()),
        ("modified", "main", ("README.md",)),
        ("untracked", "main", ("new.txt",)),
        ("staged", "main", ("added.txt",)),
        ("renamed", "main", ("RENAMED.md",)),
        ("unmerged", "main", ("README.md",)),
        ("detached_head", None, ()),
        ("path_with_space", "main", ("a file with space.txt",)),
    ],
)
def test_the_parser_reads_every_captured_checkout_state(
    name: str, branch: str | None, dirty: tuple[str, ...]
) -> None:
    assert parse_porcelain_v2(_fixture(name)) == GitStatus(
        branch=branch, head=_head_in(name), dirty=dirty
    )


def test_a_header_line_the_parser_does_not_know_is_ignored() -> None:
    text = _fixture("clean_main") + "# branch.ab +1 -0\n# future.header whatever\n"

    assert parse_porcelain_v2(text).dirty == ()


def test_a_repository_before_its_first_commit_has_no_head() -> None:
    text = "# branch.oid (initial)\n# branch.head main\n"

    assert parse_porcelain_v2(text) == GitStatus("main", None, ())


@pytest.mark.parametrize("subcommand", ["commit", "checkout", "push", "merge"])
def test_a_subcommand_outside_the_allowlist_is_refused(
    subcommand: str, tmp_path: Path
) -> None:
    assert subcommand not in GIT_SUBCOMMANDS

    with pytest.raises(ValueError, match=subcommand):
        git_read((subcommand,), tmp_path, _budget(), subprocess.run, TIMEOUT)


def test_an_option_cannot_smuggle_a_second_subcommand_past_the_allowlist(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="push"):
        git_read(("--no-pager", "push"), tmp_path, _budget(), subprocess.run, TIMEOUT)


def test_a_branch_name_that_looks_like_an_option_is_refused() -> None:
    with pytest.raises(ValueError, match="--exec"):
        is_ancestor_args("abc123", "--exec")


def test_status_reads_a_real_repository(tmp_path: Path) -> None:
    repo = make_repo(tmp_path / "repo")
    make_branch(repo, "128-slice.example")
    (repo / "new.txt").write_text("x\n")

    result = git_read(status_args(), repo, _budget(), subprocess.run, TIMEOUT)

    assert isinstance(result, GitReadResult)
    assert parse_porcelain_v2(result.stdout) == GitStatus(
        branch="128-slice.example", head=head_of(repo), dirty=("new.txt",)
    )


def test_status_of_a_detached_real_repository_has_no_branch(tmp_path: Path) -> None:
    repo = make_repo(tmp_path / "repo")
    detach_head(repo)

    result = git_read(status_args(), repo, _budget(), subprocess.run, TIMEOUT)

    assert isinstance(result, GitReadResult)
    assert parse_porcelain_v2(result.stdout).branch is None


def test_is_ancestor_exits_zero_for_a_reachable_head_and_one_otherwise(
    tmp_path: Path,
) -> None:
    repo = make_repo(tmp_path / "repo")
    make_branch(repo, "side")
    side_head = commit_file(repo, "side.txt", "x\n", "side")
    switch(repo, "main")

    ahead = git_read(
        is_ancestor_args(side_head, "main"), repo, _budget(), subprocess.run, TIMEOUT
    )
    behind = git_read(
        is_ancestor_args(head_of(repo), "side"),
        repo,
        _budget(),
        subprocess.run,
        TIMEOUT,
    )

    assert isinstance(ahead, GitReadResult) and ahead.exit_code == 1
    assert isinstance(behind, GitReadResult) and behind.exit_code == 0


def test_git_runs_without_a_prompt_and_with_stdin_closed(tmp_path: Path) -> None:
    seen: dict[str, Any] = {}

    def run(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        seen.update(kwargs, argv=argv)
        return subprocess.CompletedProcess(argv, 0, "", "")

    git_read(status_args(), tmp_path, _budget(), run, TIMEOUT)

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

    result = git_read(status_args(), tmp_path, _budget(), run, TIMEOUT)

    assert isinstance(result, GitReadFailure)
    assert "status" in result.detail


def test_a_spent_budget_starts_nothing(tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def run(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 0, "", "")

    result = git_read(status_args(), tmp_path, _budget(deadline=0.0), run, TIMEOUT)

    assert result is None
    assert calls == []
