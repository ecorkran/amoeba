"""Scenario D through the MCP tools (slice 240): the chain of
``tests/cli/test_requests_scenario.py``, every request made through ``call_tool`` in
this process. The three checkouts are registered through the CLI first, with the same
routing ``cf`` first on ``PATH`` for both doors. Every result carries the notice.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import anyio
import mcp_types as types
import pytest
from cf_routing import write_routing_cf
from cli.cli_support import write_config
from cli.requests_support import (
    CHILD,
    HASH,
    PARENT,
    Repos,
    chain_members,
    events,
    requests_by_id,
)

from amoeba.mcp import server
from amoeba.operations.quoted_data import QUOTED_DATA_NOTICE


@pytest.fixture
def repos(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Repos:
    write_config()
    found = Repos(tmp_path)
    bin_dir = tmp_path / "bin"
    write_routing_cf(bin_dir, found.projects)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    for project in found.projects:
        found.run(project, "add", "--program", "demo")
    return found


def _call(name: str, arguments: Mapping[str, object]) -> dict[str, Any]:
    async def run() -> types.CallToolResult:
        return await server.call_tool(name, arguments)

    result = anyio.run(run)
    (block,) = result.content
    assert isinstance(block, types.TextContent)
    assert not result.is_error, block.text
    document: dict[str, Any] = json.loads(block.text)
    return document


def test_the_chain_through_the_tools_and_every_result_carries_the_notice(
    repos: Repos,
) -> None:
    squadron, forge, guide = (
        str(p.path) for p in (repos.squadron, repos.forge, repos.guide)
    )
    results: list[dict[str, Any]] = []

    def call(name: str, directory: str, **arguments: object) -> dict[str, Any]:
        document = _call(name, {"directory": directory, **arguments})
        results.append(document)
        return document

    sent = call(
        "send",
        squadron,
        id=PARENT,
        to="context-forge",
        subject="add a flag",
        body="squadron needs a flag in cf",
    )
    assert sent["outcome"] == "sent"
    start = call("inbox", squadron)["as_of_seq"]
    forge_start = call("inbox", forge)["as_of_seq"]
    call("reply", forge, id=PARENT, action="accept")
    child = call(
        "send",
        forge,
        id=CHILD,
        to="ai-project-guide",
        subject="guide text",
        body="needs a section",
        parent=PARENT,
    )
    assert child["request"]["depth"] == 2
    call("reply", guide, id=CHILD, action="accept")
    call("reply", guide, id=CHILD, action="done", text="added", commit=HASH)

    forge_changes = call("inbox", forge, since=forge_start)
    assert events(forge_changes) == [(CHILD, "accepted"), (CHILD, "done")]
    call("reply", forge, id=PARENT, action="done", text="flag added")
    squadron_changes = call("inbox", squadron, since=start)
    assert events(squadron_changes) == [(PARENT, "accepted"), (PARENT, "done")]
    assert requests_by_id(squadron_changes)[PARENT]["result"] == "flag added"
    cancelled = call(
        "send", squadron, id="to-cancel", to="context-forge", subject="s", body="b"
    )
    assert cancelled["outcome"] == "sent"
    assert call("cancel", squadron, id="to-cancel")["outcome"] == "cancelled"

    assert {result["notice"] for result in results} == {QUOTED_DATA_NOTICE}


def test_list_and_status_through_the_tools_show_the_open_chain(repos: Repos) -> None:
    squadron, forge = str(repos.squadron.path), str(repos.forge.path)
    _call(
        "send",
        {
            "directory": squadron,
            "id": PARENT,
            "to": "context-forge",
            "subject": "s",
            "body": "b",
        },
    )
    _call("reply", {"directory": forge, "id": PARENT, "action": "accept"})
    _call(
        "send",
        {
            "directory": forge,
            "id": CHILD,
            "to": "ai-project-guide",
            "subject": "s",
            "body": "b",
            "parent": PARENT,
        },
    )

    listed = _call("list", {"directory": squadron})
    status = _call("status", {"directory": squadron})

    assert listed == status
    assert listed["notice"] == QUOTED_DATA_NOTICE
    forge_member = chain_members(listed)["context-forge"]
    parent = {r["id"]: r for r in forge_member["requests"]}[PARENT]
    assert parent["child_ids"] == [CHILD]
