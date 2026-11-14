"""Helpers for the rules-selection tests: small git repos and a rules-only read."""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, cast

from git_repo import commit_file, git

from amoeba.answering.passages import SourcesProblem, SourcesProblemKind
from amoeba.answering.settings import RulesChoice
from amoeba.answering.source_reads import (
    CommittedSources,
    SourceSelection,
    locate_sources,
    read_committed_sources,
)

TIMEOUT = 8.0
BIG = 10_000_000
DEFAULT_ENTRIES = ("CLAUDE.md", "AGENTS.md")

type Run = Callable[..., subprocess.CompletedProcess[str]]


def build_repo(path: Path, files: Mapping[str, str]) -> Path:
    """A repository on ``main`` holding ``files``, one commit each."""
    path.mkdir(parents=True, exist_ok=True)
    git(path, "init", "-q", "-b", "main")
    for number, (name, text) in enumerate(files.items(), start=1):
        commit_file(
            path, name, text, f"add {name}", date=f"2026-02-{number:02d}T10:00:00+00:00"
        )
    return path


def default_choice(*entries: str) -> RulesChoice:
    return RulesChoice(entries=entries or DEFAULT_ENTRIES, optional=True)


def named_choice(*entries: str) -> RulesChoice:
    return RulesChoice(entries=entries, optional=False)


def locate(
    repo: Path, rules: RulesChoice, run: Run = subprocess.run
) -> SourceSelection | SourcesProblem:
    return locate_sources(repo, "main", None, rules, run, TIMEOUT)


def read(
    repo: Path,
    rules: RulesChoice,
    *,
    max_chars: int = BIG,
    run: Run = subprocess.run,
) -> CommittedSources | SourcesProblem:
    return read_committed_sources(repo, "main", None, rules, max_chars, run, TIMEOUT)


def selected_paths(result: SourceSelection | SourcesProblem) -> list[str]:
    assert isinstance(result, SourceSelection), result
    return [chosen.path for chosen in result.files]


def read_paths(result: CommittedSources | SourcesProblem) -> list[str]:
    assert isinstance(result, CommittedSources), result
    return [file.path for file in result.files]


def problem_of(result: object, kind: SourcesProblemKind) -> SourcesProblem:
    assert isinstance(result, SourcesProblem), result
    assert result.kind is kind, result
    return result


def failing_on(subcommand: str) -> Run:
    """A ``run`` that fails every git call of ``subcommand`` and runs the rest."""

    def run(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if subcommand in argv:
            return subprocess.CompletedProcess(argv, 128, "", "fatal: injected")
        return cast("subprocess.CompletedProcess[str]", subprocess.run(argv, **kwargs))

    return run
