"""Requests between repos on two machines, with real ``cf`` and ``git`` (261, 15.4).

A CLI-only variant of the messaging walkthrough (steps 3 to 8): a real hub process, two
client homes, and the repos split across them. Each machine has its own
``CONTEXT_FORGE_DATA_DIR``, so the same kind of repo is a different Context Forge
project on each, and the real ``cf`` and ``git`` run on the client machines. The hub's
``PATH`` holds none of them. No model runs and nothing is spent.

Run it with ``uv run pytest tests/live/messaging`` (a bare ``uv run pytest`` skips
``tests/live``).
"""

from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from git_repo import git
from hub_fixture import FIRST, SECOND, ClientHome, FixtureHub, two_machine_hub
from live_environment import process_environment

from amoeba.operations.quoted_data import QUOTED_DATA_NOTICE

PROGRAM = "live-demo"
CF_TIMEOUT_SECONDS = 120
HASH = "ab12" * 10


class Machine:
    """One client machine: its home, its own Context Forge data directory, its repos."""

    def __init__(self, hub: FixtureHub, client: ClientHome) -> None:
        self.client = client
        self.data_dir = client.home / "cf-data"
        self.data_dir.mkdir()
        self.environment = {
            "PATH": os.environ["PATH"],
            "CONTEXT_FORGE_DATA_DIR": str(self.data_dir),
        }
        hub.home_environment[client.home] = self.environment

    def repo(self, name: str) -> Path:
        """A committed git repo that is a Context Forge project on this machine."""
        repo = self.client.home / "repos" / name
        repo.mkdir(parents=True)
        git(repo, "init", "-q", "-b", "main")
        (repo / "README.md").write_text(f"{name}\n", encoding="utf-8")
        git(repo, "add", "-A")
        git(repo, "commit", "-q", "-m", "seed")
        subprocess.run(
            ["cf", "init", "--lite", "--name", name],
            cwd=repo,
            env=process_environment(os.environ, **self.environment),
            capture_output=True,
            text=True,
            timeout=CF_TIMEOUT_SECONDS,
            check=True,
        )
        git(repo, "add", "-A")
        if git(repo, "status", "--porcelain").stdout.strip():
            git(repo, "commit", "-q", "-m", "cf init")
        return repo


class World:
    def __init__(self, hub: FixtureHub) -> None:
        self.alpha = Machine(hub, hub.clients[FIRST])
        self.beta = Machine(hub, hub.clients[SECOND])
        self.squadron = (self.alpha, self.alpha.repo("sq-live"))
        self.forge = (self.beta, self.beta.repo("cf-live"))
        self.guide = (self.alpha, self.alpha.repo("guide-live"))

    def run(
        self, where: tuple[Machine, Path], *args: str, expect: int = 0
    ) -> dict[str, Any]:
        machine, repo = where
        done = machine.client.run_in(repo, *args, "-j")
        assert done.code == expect, done.err + done.out
        document: dict[str, Any] = json.loads(done.out)
        return document


@pytest.fixture
def world(tmp_path: Path) -> Iterator[World]:
    with two_machine_hub(tmp_path) as hub:
        found = World(hub)
        for where in (found.squadron, found.forge, found.guide):
            added = found.run(where, "add", "--program", PROGRAM)
            assert added["outcome"] == "applied", added
        yield found


def _requests(document: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {request["id"]: request for request in document["requests"]}


def _events(document: dict[str, Any]) -> list[tuple[str, str]]:
    return [(item["message_id"], item["event"]) for item in document["deliveries"]]


def test_the_chain_across_two_machines_with_real_cf_and_git(world: World) -> None:
    squadron, forge, guide = world.squadron, world.forge, world.guide

    # Step 3: squadron (alpha) asks cf-live (beta), as text under the notice.
    machine, repo = squadron
    text = machine.client.run_in(
        repo,
        "send",
        "--id",
        "sq-1",
        "--to",
        "cf-live",
        "--subject",
        "Need X",
        "--body",
        "Please add X because Y",
    )
    assert text.code == 0, text.err
    assert text.out.splitlines()[:2] == [QUOTED_DATA_NOTICE, "sent: sq-1"]

    # Step 4: cf-live (beta) sees it, accepts, and a second accept is refused.
    inbox = world.run(forge, "inbox")
    assert _requests(inbox)["sq-1"]["direction"] == "received"
    forge_seen = inbox["as_of_seq"]
    assert world.run(forge, "reply", "sq-1", "accept")["request"]["state"] == "accepted"
    again = world.run(forge, "reply", "sq-1", "accept", expect=1)
    assert again["rejection"] == "already_accepted"
    squadron_after = world.run(squadron, "inbox")
    assert _requests(squadron_after)["sq-1"]["state"] == "accepted"

    # Step 5: cf-live asks guide-live (alpha) for what it needs first, as a child.
    child = world.run(
        forge,
        "send",
        "--id",
        "cf-1",
        "--to",
        "guide-live",
        "--subject",
        "guide text",
        "--body",
        "needs a section",
        "--parent",
        "sq-1",
    )
    assert (child["request"]["parent_id"], child["request"]["depth"]) == ("sq-1", 2)

    # Steps 6 and 7: guide-live accepts and finishes it; cf-live hears of both.
    assert _requests(world.run(guide, "inbox"))["cf-1"]["direction"] == "received"
    world.run(guide, "reply", "cf-1", "accept")
    done_child = world.run(
        guide, "reply", "cf-1", "done", "--text", "added section", "--commit", HASH
    )
    assert done_child["request"]["state"] == "done"
    forge_after = world.run(forge, "inbox", "--since", str(forge_seen))
    assert (("cf-1", "accepted") in _events(forge_after)) and (
        ("cf-1", "done") in _events(forge_after)
    )

    # Step 8: cf-live finishes the parent; squadron hears it, with the result.
    world.run(
        forge, "reply", "sq-1", "done", "--text", "X added", "--version", "v1.0.0"
    )
    final = _requests(world.run(squadron, "inbox"))["sq-1"]
    assert (final["state"], final["result"], final["result_version"]) == (
        "done",
        "X added",
        "v1.0.0",
    )


def test_each_machine_knows_the_same_kind_of_repo_by_its_own_project(
    world: World,
) -> None:
    machine, repo = world.squadron
    listed = world.run(world.squadron, "list", "members")
    by_name = {row["name"]: row for row in listed["members"]}

    assert set(by_name) == {"sq-live", "cf-live", "guide-live"}
    (checkout,) = by_name["sq-live"]["checkouts"]
    assert checkout["machine"] == FIRST
    assert checkout["path"] == str(repo.resolve())
    (other,) = by_name["cf-live"]["checkouts"]
    assert other["machine"] == SECOND
    assert machine.data_dir != world.beta.data_dir
