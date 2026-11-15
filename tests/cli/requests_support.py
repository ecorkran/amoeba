"""Three checkouts in one program and a routing ``cf`` to tell them apart, shared by the
scenario D tests (slice 240)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from cf_routing import RoutedProject

from amoeba.cli.exit_codes import EXIT_OK
from cli.cli_support import result_of, run_amoeba

HASH = "cd34" * 10
PARENT = "squadron-needs-a-flag"
CHILD = "context-forge-needs-guide-text"


class Repos:
    """The three checkouts and how to run ``amoeba`` in each."""

    def __init__(self, tmp_path: Path) -> None:
        self._tmp_path = tmp_path
        self.projects = [
            RoutedProject(f"project-{name}-id", name, tmp_path / "repos" / name)
            for name in ("squadron", "context-forge", "ai-project-guide")
        ]
        for project in self.projects:
            project.path.mkdir(parents=True)
        self.squadron, self.forge, self.guide = self.projects

    def run(
        self, repo: RoutedProject, *arguments: str, expect: int = EXIT_OK
    ) -> dict[str, Any]:
        """``amoeba <arguments> -j`` in ``repo``; the result document, after checking
        the exit code is ``expect``."""
        completed = run_amoeba(
            self._tmp_path,
            *arguments,
            as_json=True,
            cwd=repo.path,
            routing=self.projects,
        )
        assert completed.returncode == expect, completed.stderr + completed.stdout
        return result_of(completed)


def events(document: dict[str, Any]) -> list[tuple[str, str]]:
    return [(item["message_id"], item["event"]) for item in document["deliveries"]]


def requests_by_id(document: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {request["id"]: request for request in document["requests"]}


def chain_members(listed: dict[str, Any]) -> dict[str, dict[str, Any]]:
    (program,) = listed["programs"]
    return {entry["member"]["name"]: entry for entry in program["members"]}
