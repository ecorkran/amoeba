"""A temporary repository built from the frozen source fixtures (slice 143, D11)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from amoeba.runner.budget import TickBudget
from runner.git_repo import commit_file, git
from runner.observe_support import Clock, Host

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "sources"


@dataclass(frozen=True)
class SourcesRepo:
    path: Path
    #: Each repo-relative file path and the committer date it was committed with.
    dates: dict[str, datetime]


def build_sources_repo(path: Path) -> SourcesRepo:
    """Commit every fixture file at its real relative path on ``main``.

    Each commit has its own controlled date, a day apart and in a non-UTC offset, so a
    test can tell a file's date from the commit order or from the current time.
    """
    path.mkdir(parents=True, exist_ok=True)
    git(path, "init", "-q", "-b", "main")
    dates: dict[str, datetime] = {}
    files = sorted(f for f in FIXTURE_ROOT.rglob("*") if f.is_file())
    for number, file in enumerate(files, start=1):
        relative = file.relative_to(FIXTURE_ROOT).as_posix()
        stamp = f"2026-01-{number:02d}T10:00:00+02:00"
        commit_file(path, relative, file.read_text(), f"add {relative}", date=stamp)
        dates[relative] = datetime.fromisoformat(stamp)
    return SourcesRepo(path, dates)


class CountingBudget(TickBudget):
    """Counts the calls asked of it and refuses every call after ``allowed``."""

    def __init__(self, allowed: int | None = None) -> None:
        super().__init__(1_000.0, Host(), Clock().monotonic)
        self.asked = 0
        self._allowed = allowed

    def allows_call(self) -> bool:
        self.asked += 1
        return self._allowed is None or self.asked <= self._allowed
