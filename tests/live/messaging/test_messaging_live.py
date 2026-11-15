"""Requests between repos against real ``cf`` and ``git`` (slice 240, task 14.1).

Verification Walkthrough steps 3 to 8 through the CLI, then scenario D again through the
MCP tools over stdio. Three committed repos are Context Forge projects in one throwaway
data directory and members of one program in a throwaway ``AMOEBA_HOME``; no model
runs. Every ``amoeba`` call goes by the harness's absolute path with that home. The
squadron repo is the pause tier's member (its project name is ``amoeba-live-pause``).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Final

import anyio
import mcp_types as types
import yaml
from git_repo import head_of
from mcp import ClientSession, StdioServerParameters, stdio_client

from amoeba.cli.exit_codes import EXIT_OK, EXIT_REJECTED
from amoeba.config.home import store_path
from amoeba.operations.quoted_data import QUOTED_DATA_NOTICE
from live.messaging.repos import FORGE_NAME, GUIDE_NAME, SQUADRON_NAME, Toolchain
from live.pause.harness import PauseWorld, result_of, run_amoeba

MCP_SERVER: Final = Path(sys.executable).with_name("amoeba-mcp")
SESSION_TIMEOUT_SECONDS: Final = 300
LIVE_STATE: Final = Path.home() / ".local" / "state" / "amoeba"
RESUME_WAIT_SECONDS: Final = 60


def _amoeba(
    world: PauseWorld, *arguments: str, cwd: Path | None = None, expect: int = EXIT_OK
) -> dict[str, Any]:
    """``amoeba <arguments> -j`` in ``world``'s checkout; the document, after checking
    the exit code."""
    completed = run_amoeba(world, *arguments, cwd=cwd)
    assert completed.returncode == expect, (
        f"amoeba {' '.join(arguments)} exited {completed.returncode}\n"
        f"{completed.stdout}\n{completed.stderr}"
    )
    return dict(result_of(completed))


def _send(
    world: PauseWorld, request_id: str, to: str, *extra: str, expect: int = EXIT_OK
) -> dict[str, Any]:
    return _amoeba(
        world,
        "send",
        "--id",
        request_id,
        "--to",
        to,
        "--subject",
        f"subject of {request_id}",
        "--body",
        f"body of {request_id}",
        *extra,
        expect=expect,
    )


def _events(document: dict[str, Any]) -> list[tuple[str, str]]:
    return [(item["message_id"], item["event"]) for item in document["deliveries"]]


def _requests(document: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {request["id"]: request for request in document["requests"]}


def _members(listed: dict[str, Any]) -> dict[str, dict[str, Any]]:
    (program,) = listed["programs"]
    return {entry["member"]["name"]: entry for entry in program["members"]}


def test_the_store_amoeba_uses_is_the_throwaway_one(
    toolchain: Toolchain, amoeba_home: Path
) -> None:
    resolved = store_path()

    assert resolved.is_relative_to(amoeba_home)
    assert not resolved.is_relative_to(LIVE_STATE)
    listed = _amoeba(toolchain.squadron, "list")
    assert toolchain.squadron.store == resolved
    assert resolved.exists()
    assert set(_members(listed)) == {SQUADRON_NAME, FORGE_NAME, GUIDE_NAME}


def test_the_chain_from_send_to_done_through_the_cli(
    toolchain: Toolchain, tmp_path: Path
) -> None:
    squadron, forge, guide = toolchain.squadron, toolchain.forge, toolchain.guide

    # Step 3: squadron asks cf-s. The text says so, under the notice.
    text = run_amoeba(
        squadron,
        "send",
        "--id",
        "sq-1",
        "--to",
        FORGE_NAME,
        "--subject",
        "Need X",
        "--body",
        "Please add X because Y",
        as_json=False,
    )
    assert text.returncode == EXIT_OK, text.stderr
    assert text.stdout.splitlines()[:2] == [QUOTED_DATA_NOTICE, "sent: sq-1"]

    # Step 4: cf-s sees it, accepts, and a second accept is refused naming the time.
    inbox_text = run_amoeba(forge, "inbox", as_json=False).stdout
    assert inbox_text.splitlines()[0] == QUOTED_DATA_NOTICE
    assert "sq-1 · from " in inbox_text
    assert " · open · " in inbox_text
    inbox = _amoeba(forge, "inbox")
    request = _requests(inbox)["sq-1"]
    assert request["from_member"] != request["to_member"]
    assert request["direction"] == "received"
    forge_seen = inbox["as_of_seq"]
    assert _amoeba(forge, "reply", "sq-1", "accept")["request"]["state"] == "accepted"
    again = _amoeba(forge, "reply", "sq-1", "accept", expect=EXIT_REJECTED)
    assert again["rejection"] == "already_accepted"
    assert "was already accepted at " in again["problems"][0]

    # Step 5: cf-s asks guide-s for what it needs first, as a child of sq-1.
    child = _send(forge, "cf-1", GUIDE_NAME, "--parent", "sq-1")
    assert (child["request"]["parent_id"], child["request"]["depth"]) == ("sq-1", 2)
    _amoeba(guide, "reply", "cf-1", "accept")
    commit = head_of(guide.repo)
    done_child = _amoeba(
        guide, "reply", "cf-1", "done", "--text", "added Z", "--commit", commit
    )
    assert done_child["request"]["result_commit"] == commit

    # Step 6: cf-s hears of the child, from its own cursor, then finishes the parent.
    after = _amoeba(forge, "inbox", "--since", "0")
    assert ("cf-1", "done") in _events(after)
    assert after["as_of_seq"] >= forge_seen
    next_since = _amoeba(forge, "inbox", "--since", str(after["as_of_seq"]))
    assert next_since["deliveries"] == []
    done_parent = _amoeba(
        forge, "reply", "sq-1", "done", "--text", "X is in", "--version", "v1"
    )
    assert done_parent["request"]["state"] == "done"

    # Step 7: squadron sees the result; from any directory, nothing is open.
    squadron_inbox = _amoeba(squadron, "inbox")
    result = _requests(squadron_inbox)["sq-1"]
    assert (result["state"], result["result"], result["result_version"]) == (
        "done",
        "X is in",
        "v1",
    )
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    listed = _amoeba(squadron, "list", cwd=elsewhere)
    assert all(not entry["requests"] for entry in _members(listed).values())
    # The refused second accept of step 4 is still held, shown under cf-s: that is
    # message text, so the notice is set while no request is.
    (call,) = _members(listed)[FORGE_NAME]["rejected_calls"]
    assert (call["operation"], call["code"], call["message_id"]) == (
        "reply",
        "already_accepted",
        "sq-1",
    )
    assert listed["notice"] == QUOTED_DATA_NOTICE


def test_the_exits_through_the_cli(toolchain: Toolchain, tmp_path: Path) -> None:
    squadron, forge = toolchain.squadron, toolchain.forge
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()

    # Step 8a: the same id with a different body is refused.
    _send(squadron, "sq-1", FORGE_NAME)
    reused = _amoeba(
        squadron,
        "send",
        "--id",
        "sq-1",
        "--to",
        FORGE_NAME,
        "--subject",
        "subject of sq-1",
        "--body",
        "another body",
        expect=EXIT_REJECTED,
    )
    assert reused["rejection"] == "id_reused"

    # Step 8b: a fresh open request cancelled by id from a directory in no member;
    # both repos are told.
    _send(squadron, "sq-2", FORGE_NAME)
    cancelled = _amoeba(squadron, "cancel", "sq-2", cwd=elsewhere)
    assert cancelled["request"]["state"] == "cancelled"
    assert cancelled["request"]["direction"] is None
    for world in (squadron, forge):
        assert ("sq-2", "cancelled") in _events(_amoeba(world, "inbox", "--since", "0"))

    # Step 8c: removing cf-s after it was sent a request cancels it, with a reason,
    # and tells the surviving repo.
    _send(squadron, "sq-3", FORGE_NAME)
    removed = _amoeba(forge, "rm")
    assert removed["outcome"] == "applied"
    inbox = _amoeba(squadron, "inbox", "--since", "0")
    request = _requests(inbox)["sq-3"]
    assert (request["state"], request["reason"]) == ("cancelled", "member_removed")
    assert ("sq-3", "cancelled") in _events(inbox)


def _lower_resume_wait(world: PauseWorld) -> None:
    """``amoeba-mcp`` refuses a ``resume_wait_seconds`` whose ``answer`` bound reaches
    its call deadline, so the pause tier's value is lowered, as the MCP tier does."""
    config_file = world.amoeba_home / "config.yaml"
    config = yaml.safe_load(config_file.read_text(encoding="utf-8"))
    config["resume_wait_seconds"] = RESUME_WAIT_SECONDS
    config_file.write_text(yaml.safe_dump(config), encoding="utf-8")


def _server(world: PauseWorld) -> StdioServerParameters:
    return StdioServerParameters(
        command=str(MCP_SERVER), args=[], env=world.environ, cwd=world.repo.parent
    )


def test_the_chain_through_the_mcp_tools(toolchain: Toolchain) -> None:
    squadron, forge, guide = toolchain.squadron, toolchain.forge, toolchain.guide
    _lower_resume_wait(squadron)
    notices: list[str] = []

    async def scenario() -> dict[str, dict[str, Any]]:
        results: dict[str, dict[str, Any]] = {}
        with anyio.fail_after(SESSION_TIMEOUT_SECONDS):
            async with stdio_client(_server(squadron)) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()

                    async def call(
                        key: str, tool: str, world: PauseWorld, **arguments: object
                    ) -> None:
                        result = await session.call_tool(
                            tool, {"directory": str(world.repo), **arguments}
                        )
                        assert result.is_error is False, result.content
                        (block,) = result.content
                        assert isinstance(block, types.TextContent)
                        document = json.loads(block.text)
                        assert document == result.structured_content
                        notices.append(document["notice"])
                        results[key] = document

                    await call(
                        "send",
                        "send",
                        squadron,
                        id="sq-1",
                        to=FORGE_NAME,
                        subject="Need X",
                        body="Please add X because Y",
                    )
                    await call("forge-inbox", "inbox", forge)
                    await call("accept", "reply", forge, id="sq-1", action="accept")
                    await call(
                        "child",
                        "send",
                        forge,
                        id="cf-1",
                        to=GUIDE_NAME,
                        subject="Need Z",
                        body="the guide needs Z",
                        parent="sq-1",
                    )
                    await call(
                        "guide-accept", "reply", guide, id="cf-1", action="accept"
                    )
                    await call(
                        "guide-done",
                        "reply",
                        guide,
                        id="cf-1",
                        action="done",
                        text="added Z",
                        commit=head_of(guide.repo),
                    )
                    await call("forge-after", "inbox", forge, since=0)
                    await call(
                        "done",
                        "reply",
                        forge,
                        id="sq-1",
                        action="done",
                        text="X is in",
                        version="v1",
                    )
                    await call("squadron-inbox", "inbox", squadron)
                    await call("late-cancel", "cancel", squadron, id="sq-1")
        return results

    results = anyio.run(scenario)

    assert results["send"]["outcome"] == "sent"
    assert _requests(results["forge-inbox"])["sq-1"]["direction"] == "received"
    assert results["child"]["request"]["depth"] == 2
    assert results["guide-done"]["request"]["state"] == "done"
    assert ("cf-1", "done") in _events(results["forge-after"])
    final = _requests(results["squadron-inbox"])["sq-1"]
    assert (final["state"], final["result"]) == ("done", "X is in")
    assert results["late-cancel"]["rejection"] == "not_applicable"
    assert set(notices) == {QUOTED_DATA_NOTICE}
