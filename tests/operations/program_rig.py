"""A concept repository, program values and a routed ``cf``/``git`` runner for the
program concept read (ported from slice 182's rig).

``git`` runs for real in a temporary repository; ``cf`` is replayed by argv.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from cf_plan_run import PlanCfRun, plan_cf_run
from git_repo import commit_file, git

from amoeba.answering.passages import ProgramSources, SourceFile, SourcesProblem
from amoeba.operations.program_sources import (
    AskerReads,
    ProgramRead,
    read_program_sources,
)
from amoeba.store.models import Member, MemberSettings, Program
from amoeba.store.vocabulary import RulesFrom

PROGRAM_ID = "trading"
CONCEPT_MEMBER = "trading-data"
ASKING_MEMBER = "trading-engine"
THIRD_MEMBER = "trading-ui"
CONCEPT_PATH = "docs/program-concept.md"
#: A real-format concept document: front matter, then level-2 sections.
CONCEPT_TEXT = (
    "---\ntitle: Trading program concept\n---\n\n"
    "## Contracts between projects\ntrading-data owns the market data contract.\n\n"
    "## What each project is for\ntrading-data stores prices; the engine reads them.\n"
)
CONCEPT_COMMIT_DATE = "2026-02-10T09:00:00+02:00"
LATER_COMMIT_DATE = "2026-02-20T09:00:00+02:00"
REGISTERED = datetime(2026, 11, 1, tzinfo=UTC)
TIMEOUT = 8.0
BIG = 1_000_000

#: What a faulted call does: a result to return, an exception to raise, or ``None``.
type Fault = Callable[
    [Sequence[str]], subprocess.CompletedProcess[str] | Exception | None
]


@dataclass
class RoutedRun:
    """``cf`` replayed, ``git`` real; every call is kept in ``calls``."""

    concept_repo: Path
    target: str
    project_known: bool
    fault: Fault | None
    #: Answers ``cf list ...``; a program-only test never makes those calls.
    plan: PlanCfRun
    calls: list[tuple[str, ...]] = field(default_factory=lambda: [])

    @property
    def cf_calls(self) -> list[tuple[str, ...]]:
        return [call for call in self.calls if call[0] == "cf"]

    @property
    def git_calls(self) -> list[tuple[str, ...]]:
        return [call for call in self.calls if call[0] == "git"]

    def __call__(
        self, argv: Sequence[str], **kwargs: Any
    ) -> subprocess.CompletedProcess[str]:
        self.calls.append(tuple(argv))
        if self.fault is not None:
            fault = self.fault(argv)
            if isinstance(fault, Exception):
                raise fault
            if fault is not None:
                return fault
        if argv[0] == "cf":
            return self._cf(argv)
        return cast(
            "subprocess.CompletedProcess[str]",
            subprocess.run(list(argv), **kwargs),  # noqa: PLW1510
        )

    def _cf(self, argv: Sequence[str]) -> subprocess.CompletedProcess[str]:
        if argv[1] == "list":
            return self.plan(argv)
        if argv[1] == "get":
            if not self.project_known:
                document = {"error": True, "code": "PROJECT_NOT_FOUND", "message": "no"}
                return subprocess.CompletedProcess(
                    list(argv), 1, "", json.dumps(document)
                )
            project = {
                "id": argv[-1],
                "name": argv[-1],
                "projectPath": str(self.concept_repo),
            }
            return subprocess.CompletedProcess(list(argv), 0, json.dumps(project), "")
        if argv[1:3] == ["config", "get"]:
            return subprocess.CompletedProcess(
                list(argv), 0, json.dumps({"value": self.target}), ""
            )
        raise AssertionError(f"unexpected cf call: {argv}")


def build_concept_repo(path: Path, *, text: str = CONCEPT_TEXT) -> tuple[str, datetime]:
    """A repository on ``main``: the concept committed, then one unrelated commit.

    The unrelated commit is later, so a date taken from the head instead of from the
    file's last change shows up as the wrong date. Returns the head and the concept
    commit's date.
    """
    path.mkdir(parents=True, exist_ok=True)
    git(path, "init", "-q", "-b", "main")
    commit_file(path, CONCEPT_PATH, text, "add the concept", date=CONCEPT_COMMIT_DATE)
    head = commit_file(
        path, "README.md", "unrelated\n", "later", date=LATER_COMMIT_DATE
    )
    return head, datetime.fromisoformat(CONCEPT_COMMIT_DATE)


def add_branch_with_concept(repo: Path, branch: str, text: str) -> str:
    """Commit ``text`` as the concept on a new ``branch`` and return to ``main``."""
    git(repo, "checkout", "-q", "-b", branch)
    commit = commit_file(
        repo, CONCEPT_PATH, text, f"concept on {branch}", date=LATER_COMMIT_DATE
    )
    git(repo, "checkout", "-q", "main")
    return commit


def program(
    *,
    concept_member: str | None = CONCEPT_MEMBER,
    concept_path: str | None = CONCEPT_PATH,
) -> Program:
    return Program(
        program_id=PROGRAM_ID,
        concept_member=concept_member,
        concept_path=concept_path,
        registered_at=REGISTERED,
        updated_at=REGISTERED,
    )


def member(project_id: str, *, updated: datetime = REGISTERED) -> Member:
    return Member(
        program_id=PROGRAM_ID,
        settings=MemberSettings(
            project_id=project_id,
            rules_paths=("CLAUDE.md",),
            authorize_allow=(),
            authorize_deny=(),
            rules_from=RulesFrom.NAMED,
        ),
        registered_at=REGISTERED,
        updated_at=updated,
        removed_at=None,
    )


def three_members() -> list[Member]:
    return [member(p) for p in (CONCEPT_MEMBER, ASKING_MEMBER, THIRD_MEMBER)]


@dataclass
class ProgramRig:
    """Everything one program read needs, with the asker and program adjustable."""

    repo_path: Path
    head: str
    concept_date: datetime
    run: RoutedRun
    asker_id: str
    asker_files: tuple[SourceFile, ...]
    asker_repo: Path
    asker_commit: str
    the_program: Program
    members: list[Member]

    def read(self, *, max_chars: int = BIG) -> ProgramSources | SourcesProblem:
        asker = next(m for m in self.members if m.project_id == self.asker_id)
        return read_program_sources(
            self.the_program,
            self.members,
            ProgramRead(
                asker=asker,
                asker_reads=AskerReads(
                    self.asker_repo, self.asker_commit, self.asker_files
                ),
                max_chars=max_chars,
                run=self.run,
                timeout_seconds=TIMEOUT,
            ),
        )


def build_program_rig(
    tmp_path: Path,
    *,
    asker_holds_concept: bool = False,
    asker_files: tuple[SourceFile, ...] = (),
    project_known: bool = True,
) -> ProgramRig:
    """The concept repo is the concept member's checkout; when the asker holds the
    concept it is also the asker's checkout, pinned at its head."""
    repo = tmp_path / "concept-repo"
    head, concept_date = build_concept_repo(repo)
    asker_id = CONCEPT_MEMBER if asker_holds_concept else ASKING_MEMBER
    return ProgramRig(
        repo_path=repo,
        head=head,
        concept_date=concept_date,
        run=RoutedRun(
            concept_repo=repo,
            target="main",
            project_known=project_known,
            fault=None,
            plan=plan_cf_run(integration_branch="", broken=False),
        ),
        asker_id=asker_id,
        asker_files=asker_files,
        asker_repo=repo,
        asker_commit=head,
        the_program=program(),
        members=three_members(),
    )
