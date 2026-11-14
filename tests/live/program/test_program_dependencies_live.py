"""``report-release`` and ``changes`` against real ``cf`` and ``git`` (slice 227, 6.2).

Both operations run through the CLI in a throwaway ``AMOEBA_HOME``. The consumer's
``changes`` result names the provider through the real ``cf list projects`` output, a
second worktree of the consumer resolves through real ``cf`` to the same member, and a
directory outside every member is ``not_a_member``. No model runs.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from git_repo import commit_file, git, head_of

from amoeba.cli.exit_codes import EXIT_OK, EXIT_REJECTED
from live.pause.harness import CF_PROJECT_NAME, PauseWorld, run_amoeba

EARLIEST = "2020-01-01T00:00:00+00:00"


def _report(provider: PauseWorld, commit: str, *extra: str) -> dict[str, Any]:
    completed = run_amoeba(
        provider,
        "report-release",
        "--commit",
        commit,
        "--changed",
        f"changed in {commit[:7]}",
        "--touched",
        "interface",
        *extra,
    )
    result: dict[str, Any] = json.loads(completed.stdout)
    result["exit"] = completed.returncode
    return result


def _changes(world: PauseWorld, since: str, cwd: Path | None = None) -> dict[str, Any]:
    completed = run_amoeba(world, "changes", "--since", since, cwd=cwd)
    result: dict[str, Any] = json.loads(completed.stdout)
    result["exit"] = completed.returncode
    return result


def _commits(result: dict[str, Any]) -> list[str]:
    return [
        release["commit"] for pair in result["pairs"] for release in pair["releases"]
    ]


def _now() -> str:
    return datetime.now(UTC).isoformat()


def test_report_release_records_repeats_and_rejects_through_the_cli(
    program_worlds: tuple[PauseWorld, PauseWorld],
) -> None:
    provider, _ = program_worlds
    commit = commit_file(provider.repo, "interface.txt", "v1\n", "interface")

    first = _report(provider, commit)
    again = _report(provider, commit)
    abbreviated = _report(provider, commit[:7])

    assert (first["exit"], first["outcome"]) == (EXIT_OK, "recorded")
    assert first["report"]["commit"] == commit
    assert (again["exit"], again["outcome"]) == (EXIT_OK, "unchanged")
    assert (abbreviated["exit"], abbreviated["outcome"]) == (EXIT_REJECTED, "rejected")
    assert abbreviated["problems"][0]["code"] == "malformed"


def test_changes_lists_the_report_with_the_providers_cf_name(
    program_worlds: tuple[PauseWorld, PauseWorld],
) -> None:
    provider, consumer = program_worlds
    commit = commit_file(provider.repo, "interface.txt", "v1\n", "interface")
    assert _report(provider, commit)["outcome"] == "recorded"

    result = _changes(consumer, EARLIEST)

    assert (result["exit"], result["outcome"]) == (EXIT_OK, "listed")
    (pair,) = result["pairs"]
    assert pair["provider"]["name"] == CF_PROJECT_NAME
    assert [release["commit"] for release in pair["releases"]] == [commit]
    assert result["warnings"] == []


def test_a_directory_outside_every_member_is_not_a_member(
    program_worlds: tuple[PauseWorld, PauseWorld], tmp_path: Path
) -> None:
    _, consumer = program_worlds
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()

    result = _changes(consumer, EARLIEST, cwd=elsewhere)

    assert (result["exit"], result["outcome"]) == (EXIT_REJECTED, "rejected")
    assert result["problems"][0]["code"] == "not_a_member"


def test_a_second_worktree_resolves_to_the_same_member_and_sees_its_own_window(
    program_worlds: tuple[PauseWorld, PauseWorld], tmp_path: Path
) -> None:
    provider, consumer = program_worlds
    worktree = tmp_path / "consumer-worktree"
    git(consumer.repo, "worktree", "add", "-q", "-b", "other", str(worktree))
    assert head_of(worktree) == head_of(consumer.repo)

    before_first = _now()
    first = commit_file(provider.repo, "one.txt", "1\n", "one")
    assert _report(provider, first)["outcome"] == "recorded"
    between = _now()
    second = commit_file(provider.repo, "two.txt", "2\n", "two")
    assert _report(provider, second)["outcome"] == "recorded"

    main_checkout = _changes(consumer, before_first)
    other_checkout = _changes(consumer, between, cwd=worktree)

    assert other_checkout["member"] == main_checkout["member"]
    assert _commits(main_checkout) == [first, second]
    assert _commits(other_checkout) == [second]
