"""Scenario D through the CLI (slice 240): squadron asks context-forge for a change,
which needs one from ai-project-guide. Three real checkouts in one program, a routing
``cf`` that tells them apart, and the real ``amoeba`` script for every step.

The chain: squadron sends, context-forge accepts and sends a child to ai-project-guide
(``--parent``), ai-project-guide accepts and finishes it, context-forge finishes the
parent. Each party's ``inbox`` (with ``--since`` and the ``as_of_seq`` it was last
given) shows each change; ``list`` shows the chain while it is open and nothing after.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from cf_routing import RoutedProject
from store_open import open_local_store
from user_configs import user_config

from amoeba.cli.exit_codes import EXIT_REJECTED
from amoeba.config.home import store_path
from amoeba.operations.quoted_data import QUOTED_DATA_NOTICE
from amoeba.store.notes import NewNote, insert_note
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


@pytest.fixture
def repos(tmp_path: Path) -> Repos:
    write_config()
    found = Repos(tmp_path)
    for project in found.projects:
        found.run(project, "add", "--program", "demo")
    return found


def test_the_chain_from_send_to_done_is_seen_by_every_party(repos: Repos) -> None:
    squadron, forge, guide = repos.squadron, repos.forge, repos.guide

    # Squadron asks context-forge. Each party starts from an empty inbox.
    sent = repos.run(
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
    assert sent["request"]["to_member"] == repos.member_id(forge)
    forge_inbox = repos.run(forge, "inbox")
    assert requests_by_id(forge_inbox)[PARENT]["direction"] == "received"
    assert requests_by_id(forge_inbox)[PARENT]["state"] == "open"
    forge_seen = forge_inbox["as_of_seq"]
    assert repos.run(squadron, "inbox")["as_of_seq"] == forge_seen
    squadron_seen = forge_seen

    # Context-forge accepts, then asks ai-project-guide for what it needs first.
    accepted = repos.run(forge, "reply", PARENT, "accept")
    assert accepted["request"]["state"] == "accepted"
    child = repos.run(
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

    squadron_after_accept = repos.run(squadron, "inbox", "--since", str(squadron_seen))
    assert events(squadron_after_accept) == [(PARENT, "accepted")]
    assert requests_by_id(squadron_after_accept)[PARENT]["state"] == "accepted"
    squadron_seen = squadron_after_accept["as_of_seq"]

    # While the chain is open, list shows the parent waiting on the child.
    listed = repos.run(squadron, "list")
    assert listed["notice"] == QUOTED_DATA_NOTICE
    by_name = chain_members(listed)
    forge_requests = {r["id"]: r for r in by_name["context-forge"]["requests"]}
    assert forge_requests[PARENT]["child_ids"] == [CHILD]
    assert forge_requests[PARENT]["state"] == "accepted"
    assert forge_requests[CHILD]["child_ids"] == []
    assert {r["id"] for r in by_name["ai-project-guide"]["requests"]} == {CHILD}
    assert {r["id"] for r in by_name["squadron"]["requests"]} == {PARENT}

    # Ai-project-guide accepts and finishes the child.
    guide_inbox = repos.run(guide, "inbox")
    assert requests_by_id(guide_inbox)[CHILD]["direction"] == "received"
    repos.run(guide, "reply", CHILD, "accept")
    done_child = repos.run(
        guide, "reply", CHILD, "done", "--text", "added section 4", "--commit", HASH
    )
    assert done_child["request"]["state"] == "done"

    # Context-forge hears of both changes to the child, in order, then finishes.
    forge_after = repos.run(forge, "inbox", "--since", str(forge_seen))
    assert events(forge_after) == [(CHILD, "accepted"), (CHILD, "done")]
    assert requests_by_id(forge_after)[CHILD]["result_commit"] == HASH
    repos.run(
        forge, "reply", PARENT, "done", "--text", "flag added", "--version", "v2.0.0"
    )

    # Squadron hears the parent is done, with the result.
    squadron_final = repos.run(squadron, "inbox", "--since", str(squadron_seen))
    assert events(squadron_final) == [(PARENT, "done")]
    result = requests_by_id(squadron_final)[PARENT]
    assert (result["state"], result["result"], result["result_version"]) == (
        "done",
        "flag added",
        "v2.0.0",
    )

    # Nothing is left open: list shows no request and no notice.
    after = repos.run(squadron, "list")
    assert after["notice"] is None
    assert all(not entry["requests"] for entry in chain_members(after).values())
    # Held until pruned, the finished chain is still in each inbox.
    assert set(requests_by_id(repos.run(forge, "inbox"))) == {PARENT, CHILD}


def test_a_rejection_in_the_chain_is_recorded_and_shown_under_its_member(
    repos: Repos,
) -> None:
    rejected = repos.run(
        repos.squadron,
        "send",
        "--id",
        PARENT,
        "--to",
        "nobody-here",
        "--subject",
        "s",
        "--body",
        "b",
        expect=EXIT_REJECTED,
    )
    assert rejected["rejection"] == "unknown_recipient"

    listed = repos.run(repos.squadron, "list")

    assert listed["notice"] == QUOTED_DATA_NOTICE
    (call,) = chain_members(listed)["squadron"]["rejected_calls"]
    assert (call["operation"], call["code"], call["to_ref"]) == (
        "send",
        "unknown_recipient",
        "nobody-here",
    )


def test_a_chain_too_deep_send_is_recorded_and_shown_in_list_under_the_sender(
    repos: Repos,
) -> None:
    depth_limit = user_config().max_chain_depth
    sent: list[str] = []
    for number in range(depth_limit):
        request_id = f"link-{number}"
        extra = ("--parent", sent[-1]) if sent else ()
        repos.run(
            repos.squadron,
            "send",
            "--id",
            request_id,
            "--to",
            "context-forge",
            "--subject",
            "s",
            "--body",
            "b",
            *extra,
        )
        sent.append(request_id)

    too_deep = repos.run(
        repos.squadron,
        "send",
        "--id",
        "one-more",
        "--to",
        "context-forge",
        "--subject",
        "s",
        "--body",
        "b",
        "--parent",
        sent[-1],
        expect=EXIT_REJECTED,
    )

    assert too_deep["rejection"] == "chain_too_deep"
    assert str(depth_limit) in too_deep["problems"][0]
    listed = repos.run(repos.squadron, "list")
    calls = chain_members(listed)["squadron"]["rejected_calls"]
    assert [(call["code"], call["message_id"]) for call in calls] == [
        ("chain_too_deep", "one-more")
    ]
    assert listed["notice"] == QUOTED_DATA_NOTICE


def test_a_reply_by_a_non_addressee_is_recorded_and_shown_under_the_caller(
    repos: Repos,
) -> None:
    repos.run(
        repos.squadron,
        "send",
        "--id",
        PARENT,
        "--to",
        "context-forge",
        "--subject",
        "s",
        "--body",
        "b",
    )

    refused = repos.run(repos.guide, "reply", PARENT, "accept", expect=EXIT_REJECTED)

    assert refused["rejection"] == "not_addressee"
    listed = repos.run(repos.squadron, "list")
    (call,) = chain_members(listed)["ai-project-guide"]["rejected_calls"]
    assert (call["operation"], call["code"], call["message_id"]) == (
        "reply",
        "not_addressee",
        PARENT,
    )
    assert requests_by_id(repos.run(repos.forge, "inbox"))[PARENT]["state"] == "open"


def _write_note(
    repos: Repos,
    note_id: str,
    sender: RoutedProject,
    recipients: list[RoutedProject],
    **to: str,
) -> None:
    """A note written into the CLI's own store, as ``send --note`` will (243 6.1)."""
    note = NewNote(
        note_id,
        repos.member_id(sender),
        to.get("to_member"),
        to.get("to_program"),
        "news",
        "not a request",
    )
    with open_local_store(store_path()) as store, store.write() as transaction:
        insert_note(
            transaction,
            note,
            [repos.member_id(r) for r in recipients],
            datetime.now(UTC),
        )


def _request_events(document: dict[str, Any]) -> list[tuple[str, str]]:
    return [pair for pair in events(document) if not pair[0].startswith("note-")]


def test_notes_in_the_store_leave_the_request_chain_unchanged(repos: Repos) -> None:
    """Scenario D again, with a program note sent first and a direct note in the
    middle: every request result and every inbox request list is as without them."""
    squadron, forge, guide = repos.squadron, repos.forge, repos.guide
    _write_note(repos, "note-program", squadron, [forge, guide], to_program="demo")

    sent = repos.run(
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
    assert sent["outcome"] == "sent" and sent["request"]["state"] == "open"
    forge_inbox = repos.run(forge, "inbox")
    assert set(requests_by_id(forge_inbox)) == {PARENT}
    assert [note["id"] for note in forge_inbox["notes"]] == ["note-program"]
    forge_seen = forge_inbox["as_of_seq"]

    accepted = repos.run(forge, "reply", PARENT, "accept")
    assert accepted["request"]["state"] == "accepted"
    child = repos.run(
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
    _write_note(repos, "note-direct", guide, [forge], to_member=repos.member_id(forge))

    guide_inbox = repos.run(guide, "inbox")
    assert set(requests_by_id(guide_inbox)) == {CHILD}
    repos.run(guide, "reply", CHILD, "accept")
    done_child = repos.run(
        guide, "reply", CHILD, "done", "--text", "added section 4", "--commit", HASH
    )
    assert done_child["request"]["state"] == "done"

    forge_after = repos.run(forge, "inbox", "--since", str(forge_seen))
    assert _request_events(forge_after) == [(CHILD, "accepted"), (CHILD, "done")]
    assert set(requests_by_id(forge_after)) == {CHILD}
    assert [note["id"] for note in forge_after["notes"]] == ["note-direct"]
    done = repos.run(
        forge, "reply", PARENT, "done", "--text", "flag added", "--version", "v2.0.0"
    )
    assert done["request"]["state"] == "done"

    assert set(requests_by_id(repos.run(forge, "inbox"))) == {PARENT, CHILD}
    assert {n["id"] for n in repos.run(forge, "inbox")["notes"]} == {
        "note-program",
        "note-direct",
    }
    listed = repos.run(squadron, "list")
    assert listed["notice"] is None
    assert all(not entry["requests"] for entry in chain_members(listed).values())
