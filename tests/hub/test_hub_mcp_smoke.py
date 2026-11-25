"""``amoeba-mcp`` over real stdio on a joined machine, against the real hub (slice 263,
8.1): a session on ``beta`` says which machine it is on and shows in ``list -j`` from
``alpha``."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import anyio
import pytest
from hub_clients import HTTPS_ORIGIN
from hub_fixture import FIRST, SECOND, FixtureHub, two_machine_hub

NAME = "core"


@pytest.fixture
def hub(tmp_path: Path) -> Iterator[FixtureHub]:
    with two_machine_hub(tmp_path) as running:
        yield running


def _sessions(listed: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        session
        for program in listed["programs"]
        for member in program["members"]
        for session in member["sessions"]
    ]


def test_a_session_on_beta_names_its_machine_and_shows_from_alpha(
    hub: FixtureHub,
) -> None:
    alpha, beta = hub.clients[FIRST], hub.clients[SECOND]
    repo = beta.clone(NAME, HTTPS_ORIGIN, "cf-core-b", NAME)
    added = beta.run_in(repo, "add", "-j")
    assert added.code == 0, added.err + added.out
    seen: list[dict[str, Any]] = []

    async def scenario() -> str:
        async with beta.mcp(repo) as run:
            line = await run.wait_for_presence(SECOND)

            for _ in range(100):
                done = await anyio.to_thread.run_sync(lambda: alpha.run("list", "-j"))
                assert done.code == 0, done.err
                seen.extend(_sessions(json.loads(done.out)))
                if seen:
                    break
                await anyio.sleep(0.2)
            return line

    line = anyio.run(scenario)

    assert "machine beta" in line
    (session,) = seen
    assert session["machine"] == SECOND
    assert session["directory"] == str(repo)
