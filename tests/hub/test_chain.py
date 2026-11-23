"""240's three-repo request chain by CLI, with the repos split across two machines
(slice 261, 15.2). Squadron and ai-project-guide are on ``alpha``, context-forge on
``beta``; each step is followed by ``inbox`` from the other machine. No wake commands,
so every ``send``, the child with its ``parent`` included, is served."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from cli.requests_support import CHILD, HASH, PARENT, events, requests_by_id
from hub_fixture import FIRST, SECOND, ClientHome, FixtureHub, two_machine_hub

PROGRAM = "demo"


class Chain:
    """The three repos, each on its machine, and how to run ``amoeba`` in them."""

    def __init__(self, hub: FixtureHub) -> None:
        alpha, beta = hub.clients[FIRST], hub.clients[SECOND]
        self.squadron = (alpha, alpha.clone("squadron", None, "cf-squadron-a"))
        self.forge = (beta, beta.clone("context-forge", None, "cf-forge-b"))
        self.guide = (alpha, alpha.clone("ai-project-guide", None, "cf-guide-a"))

    def run(
        self, where: tuple[ClientHome, Path], *args: str, expect: int = 0
    ) -> dict[str, Any]:
        client, repo = where
        done = client.run_in(repo, *args, "-j")
        assert done.code == expect, done.err + done.out
        document: dict[str, Any] = json.loads(done.out)
        return document


@pytest.fixture
def chain(tmp_path: Path) -> Iterator[Chain]:
    with two_machine_hub(tmp_path) as hub:
        found = Chain(hub)
        for where in (found.squadron, found.forge, found.guide):
            added = found.run(where, "add", "--program", PROGRAM)
            assert added["outcome"] == "applied", added
        yield found


def test_the_chain_from_send_to_done_is_seen_by_every_party_across_two_machines(
    chain: Chain,
) -> None:
    squadron, forge, guide = chain.squadron, chain.forge, chain.guide

    sent = chain.run(
        squadron,
        "send",
        "--id",
        PARENT,
        "--to",
        "context-forge",
        "--subject",
        "add a flag",
        "--body",
        "squadron needs a flag in cf",
    )
    assert sent["outcome"] == "sent"
    forge_inbox = chain.run(forge, "inbox")
    assert requests_by_id(forge_inbox)[PARENT]["direction"] == "received"
    assert requests_by_id(forge_inbox)[PARENT]["state"] == "open"
    forge_seen = forge_inbox["as_of_seq"]
    squadron_seen = chain.run(squadron, "inbox")["as_of_seq"]

    accepted = chain.run(forge, "reply", PARENT, "accept")
    assert accepted["request"]["state"] == "accepted"
    squadron_after = chain.run(squadron, "inbox", "--since", str(squadron_seen))
    assert events(squadron_after) == [(PARENT, "accepted")]
    squadron_seen = squadron_after["as_of_seq"]

    child = chain.run(
        forge,
        "send",
        "--id",
        CHILD,
        "--to",
        "ai-project-guide",
        "--subject",
        "guide text",
        "--body",
        "context-forge needs a guide section",
        "--parent",
        PARENT,
    )
    assert (child["request"]["parent_id"], child["request"]["depth"]) == (PARENT, 2)
    guide_inbox = chain.run(guide, "inbox")
    assert requests_by_id(guide_inbox)[CHILD]["direction"] == "received"

    chain.run(guide, "reply", CHILD, "accept")
    done_child = chain.run(
        guide, "reply", CHILD, "done", "--text", "added section 4", "--commit", HASH
    )
    assert done_child["request"]["state"] == "done"
    forge_after = chain.run(forge, "inbox", "--since", str(forge_seen))
    assert events(forge_after) == [(CHILD, "accepted"), (CHILD, "done")]
    assert requests_by_id(forge_after)[CHILD]["result_commit"] == HASH

    chain.run(
        forge, "reply", PARENT, "done", "--text", "flag added", "--version", "v2.0.0"
    )
    squadron_final = chain.run(squadron, "inbox", "--since", str(squadron_seen))
    assert events(squadron_final) == [(PARENT, "done")]
    result = requests_by_id(squadron_final)[PARENT]
    assert (result["state"], result["result"], result["result_version"]) == (
        "done",
        "flag added",
        "v2.0.0",
    )


def test_a_rejection_by_the_hub_part_is_shown_and_recorded_on_the_hub(
    chain: Chain,
) -> None:
    rejected = chain.run(
        chain.squadron,
        "send",
        "--id",
        PARENT,
        "--to",
        "nobody-here",
        "--subject",
        "s",
        "--body",
        "b",
        expect=1,
    )

    assert rejected["rejection"] == "unknown_recipient"
    listed = chain.run(chain.forge, "list")
    assert listed["notice"] is not None
