"""Committed source reads (slice 143, D1/D2/D5/D7) against a real repository."""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import pytest

from amoeba.runner.answering.passages import (
    PassageKind,
    SourcesProblem,
    SourcesProblemKind,
)
from amoeba.runner.answering.source_reads import (
    CommittedSources,
    SliceRef,
    SourceSelection,
    locate_sources,
    read_committed_sources,
)
from amoeba.runner.budget import TickBudget
from runner.answering.sources_repo import FIXTURE_ROOT, SourcesRepo, build_sources_repo
from runner.git_repo import commit_file, git, head_of
from runner.observe_support import Clock, Host

TIMEOUT = 8.0
RULES_DIR = "project-documents/ai-project-guide/project-guides/rules"
RULES = ("CLAUDE.md", f"{RULES_DIR}/*.md")
SLICE = SliceRef(slice_index=132, initiative_index=120)
BIG = 10_000_000

#: Offer order for slice 132 of initiative 120 with RULES (D1, D10).
SLICE_132_PATHS = [
    "CLAUDE.md",
    f"{RULES_DIR}/git.md",
    f"{RULES_DIR}/python.md",
    "project-documents/user/project-guides/000-concept.amoeba.md",
    "project-documents/user/project-guides/001-initiative-plan.amoeba.md",
    "project-documents/user/architecture/120-arch.runner-routing-engine.md",
    "project-documents/user/architecture/120-slices.runner-routing-engine.md",
    "project-documents/user/slices/132-slice.pipeline-supervisor.md",
    "project-documents/user/tasks/132-tasks.pipeline-supervisor.md",
]
#: 2 + L + 2F for the fixture: L = 6 listings (root, rules directory, four plan
#: directories), F = 9 files, so 2 + 6 + 2 * 9.
SLICE_132_CALLS = 26


class CountingBudget(TickBudget):
    """Counts the calls asked of it and refuses every call after ``allowed``."""

    def __init__(self, allowed: int | None = None) -> None:
        super().__init__(1_000.0, Host(), Clock().monotonic)
        self.asked = 0
        self._allowed = allowed

    def allows_call(self) -> bool:
        self.asked += 1
        return self._allowed is None or self.asked <= self._allowed


def _budget() -> TickBudget:
    return TickBudget(1_000.0, Host(), Clock().monotonic)


@pytest.fixture(scope="module")
def sources(tmp_path_factory: pytest.TempPathFactory) -> SourcesRepo:
    return build_sources_repo(tmp_path_factory.mktemp("sources") / "repo")


def _locate(
    repo: Path,
    *,
    rules: tuple[str, ...] = RULES,
    slice_ref: SliceRef = SLICE,
    target: str = "main",
    budget: TickBudget | None = None,
    run: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> SourceSelection | SourcesProblem | None:
    return locate_sources(
        repo, target, slice_ref, rules, budget or _budget(), run, TIMEOUT
    )


def _read(
    repo: Path,
    *,
    rules: tuple[str, ...] = RULES,
    max_chars: int = BIG,
    budget: TickBudget | None = None,
    run: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> CommittedSources | SourcesProblem | None:
    return read_committed_sources(
        repo, "main", SLICE, rules, max_chars, budget or _budget(), run, TIMEOUT
    )


def _paths(selection: SourceSelection | SourcesProblem | None) -> list[str]:
    assert isinstance(selection, SourceSelection)
    return [chosen.path for chosen in selection.files]


def _problem(result: object, kind: SourcesProblemKind) -> SourcesProblem:
    assert isinstance(result, SourcesProblem), result
    assert result.kind is kind
    return result


def _real(argv: list[str], kwargs: dict[str, Any]) -> subprocess.CompletedProcess[str]:
    return cast("subprocess.CompletedProcess[str]", subprocess.run(argv, **kwargs))


def _intercept(
    when: Callable[[list[str]], bool], reply: subprocess.CompletedProcess[str]
) -> Callable[..., subprocess.CompletedProcess[str]]:
    """A ``run`` that answers matching commands with ``reply``; others run for real."""

    def run(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if when(argv):
            return subprocess.CompletedProcess(
                argv, reply.returncode, reply.stdout, "x"
            )
        return _real(argv, kwargs)

    return run


# Locate and select


def test_slice_132_selects_rules_then_the_plan_in_table_order(
    sources: SourcesRepo,
) -> None:
    selection = _locate(sources.path)

    assert _paths(selection) == SLICE_132_PATHS
    assert isinstance(selection, SourceSelection)
    assert selection.commit == head_of(sources.path)
    kinds = [chosen.kind for chosen in selection.files]
    assert kinds == [PassageKind.RULE] * 3 + [PassageKind.PLAN] * 6


def test_a_file_chosen_twice_appears_once_at_its_first_position(
    sources: SourcesRepo,
) -> None:
    design = "project-documents/user/slices/132-slice.pipeline-supervisor.md"
    rules = (
        "CLAUDE.md",
        f"{RULES_DIR}/git.md",
        f"{RULES_DIR}/*.md",
        design,
        "CLAUDE.md",
    )

    selection = _locate(sources.path, rules=rules)

    paths = _paths(selection)
    assert paths[:4] == [
        "CLAUDE.md",
        f"{RULES_DIR}/git.md",
        f"{RULES_DIR}/python.md",
        design,
    ]
    assert len(paths) == len(set(paths)) == 9
    assert isinstance(selection, SourceSelection)
    assert selection.files[3].kind is PassageKind.RULE


def test_a_commit_added_after_the_first_call_is_not_mixed_in(
    sources: SourcesRepo, tmp_path: Path
) -> None:
    repo = build_sources_repo(tmp_path / "repo")
    pinned = head_of(repo.path)
    calls: list[int] = []

    def run(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        answer = _real(argv, kwargs)
        calls.append(1)
        if len(calls) == 1:  # the target has moved on before the second read
            commit_file(repo.path, "CLAUDE.md", "CHANGED\n", "later")
        return answer

    result = _read(repo.path, run=run)

    assert isinstance(result, CommittedSources)
    assert result.commit == pinned
    assert result.files[0].text == (FIXTURE_ROOT / "CLAUDE.md").read_text()
    assert head_of(repo.path) != pinned


def test_no_slice_plan_is_sources_missing(sources: SourcesRepo) -> None:
    result = _locate(sources.path, slice_ref=SliceRef(132, 999))

    assert "999" in _problem(result, SourcesProblemKind.MISSING).detail


def test_no_design_and_no_tasks_yields_the_rest(sources: SourcesRepo) -> None:
    paths = _paths(_locate(sources.path, slice_ref=SliceRef(133, 120)))

    assert paths == SLICE_132_PATHS[:7]


def test_a_rules_entry_that_matches_nothing_is_missing_and_named(
    sources: SourcesRepo,
) -> None:
    entry = f"{RULES_DIR}/*.txt"

    result = _locate(sources.path, rules=("CLAUDE.md", entry))

    assert entry in _problem(result, SourcesProblemKind.MISSING).detail


def test_a_rules_entry_in_a_missing_directory_is_unreadable_and_named(
    sources: SourcesRepo,
) -> None:
    result = _locate(sources.path, rules=("nope/rules.md",))

    assert "nope/rules.md" in _problem(result, SourcesProblemKind.UNREADABLE).detail


def test_an_absent_plan_directory_matches_nothing(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    commit_file(
        repo, "project-documents/user/architecture/120-slices.x.md", "# S\n", "s"
    )
    commit_file(repo, "CLAUDE.md", "# Rules\n", "r")

    paths = _paths(_locate(repo, rules=("CLAUDE.md",)))

    assert paths == ["CLAUDE.md", "project-documents/user/architecture/120-slices.x.md"]


def test_a_target_that_does_not_resolve_is_unreadable(sources: SourcesRepo) -> None:
    result = _locate(sources.path, target="no-such-branch")

    assert "no-such-branch" in _problem(result, SourcesProblemKind.UNREADABLE).detail


# Reading files


def test_each_file_has_its_committed_text_and_controlled_date(
    sources: SourcesRepo,
) -> None:
    result = _read(sources.path)

    assert isinstance(result, CommittedSources)
    assert [file.path for file in result.files] == SLICE_132_PATHS
    for file in result.files:
        assert file.date == sources.dates[file.path]
        assert file.text == (FIXTURE_ROOT / file.path).read_text()


def test_an_uncommitted_edit_and_an_untracked_file_are_invisible(
    tmp_path: Path,
) -> None:
    repo = build_sources_repo(tmp_path / "repo")
    (repo.path / "CLAUDE.md").write_text("EDITED, NOT COMMITTED\n")
    (repo.path / RULES_DIR / "untracked.md").write_text("# Untracked\n")

    result = _read(repo.path)

    assert isinstance(result, CommittedSources)
    assert [file.path for file in result.files] == SLICE_132_PATHS
    assert result.files[0].text == (FIXTURE_ROOT / "CLAUDE.md").read_text()


def test_a_failing_show_of_a_listed_file_is_unreadable_not_a_smaller_set(
    sources: SourcesRepo,
) -> None:
    def fails(argv: list[str]) -> bool:
        return "show" in argv and argv[-1].endswith(":CLAUDE.md")

    run = _intercept(fails, subprocess.CompletedProcess([], 128, "", ""))

    result = _read(sources.path, run=run)

    assert "CLAUDE.md" in _problem(result, SourcesProblemKind.UNREADABLE).detail


def test_a_non_utf8_file_matched_by_a_glob_is_unreadable_and_named(
    tmp_path: Path,
) -> None:
    repo = build_sources_repo(tmp_path / "repo")
    binary = repo.path / RULES_DIR / "binary.md"
    binary.write_bytes(b"\xff\xfe\x00 not text \x80")
    git(repo.path, "add", "-f", "--", f"{RULES_DIR}/binary.md")
    git(repo.path, "commit", "-q", "-m", "binary")

    result = _read(repo.path)

    assert "binary.md" in _problem(result, SourcesProblemKind.UNREADABLE).detail


@pytest.mark.parametrize(
    ("code", "output"), [(1, "2026-01-01T00:00:00+00:00\n"), (0, ""), (0, "garbage\n")]
)
def test_an_unreadable_date_never_falls_back(
    sources: SourcesRepo, code: int, output: str
) -> None:
    def date_of_claude(argv: list[str]) -> bool:
        return "log" in argv and "--format=%cI" in argv and argv[-1] == "CLAUDE.md"

    run = _intercept(date_of_claude, subprocess.CompletedProcess([], code, output, ""))

    result = _read(sources.path, run=run)

    assert "CLAUDE.md" in _problem(result, SourcesProblemKind.UNREADABLE).detail


# Budget and size


def test_the_fixture_read_makes_exactly_the_documented_number_of_calls(
    sources: SourcesRepo,
) -> None:
    budget = CountingBudget()

    result = _read(sources.path, budget=budget)

    assert isinstance(result, CommittedSources)
    assert budget.asked == SLICE_132_CALLS


def test_a_budget_allowing_exactly_that_many_calls_completes(
    sources: SourcesRepo,
) -> None:
    result = _read(sources.path, budget=CountingBudget(allowed=SLICE_132_CALLS))

    assert isinstance(result, CommittedSources)


@pytest.mark.parametrize("refused", range(1, SLICE_132_CALLS + 1))
def test_a_budget_refusing_any_one_call_returns_none(
    sources: SourcesRepo, refused: int
) -> None:
    assert _read(sources.path, budget=CountingBudget(allowed=refused - 1)) is None


def test_an_oversized_set_stops_reading_early(sources: SourcesRepo) -> None:
    budget = CountingBudget()

    result = _read(sources.path, max_chars=100, budget=budget)

    detail = _problem(result, SourcesProblemKind.TOO_LARGE).detail
    assert "at least" in detail and "100" in detail
    assert budget.asked < SLICE_132_CALLS
