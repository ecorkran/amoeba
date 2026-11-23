"""Members by name, through the door, on two machines (slice 261, 15.3, D7, D15).

``alpha`` and ``beta`` each have their own stub ``cf`` (a repo has a different project
id on each) and their own clone of it, ``origin`` in the SSH form on one and the HTTPS
form on the other. Every command is the real CLI; the hub is a real process.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

import pytest
from hub_clients import HTTPS_ORIGIN, SSH_ORIGIN
from hub_fixture import (
    FIRST,
    SECOND,
    ClientHome,
    FixtureHub,
    hub_layout,
    two_machine_hub,
)
from store.schema_11 import OldMember, build_schema_11_store

from amoeba.client.call import call
from amoeba.client.client_file import load_client_file
from amoeba.client.errors import HubRefusedError
from amoeba.wire.protocol import RefusalCode

REDUCED = "github.com/org/shared-repo"
NAME = "shared-repo"


@pytest.fixture
def hub(tmp_path: Path) -> Iterator[FixtureHub]:
    with two_machine_hub(tmp_path) as running:
        yield running


def run(client: ClientHome, where: Path, *args: str, expect: int = 0) -> dict[str, Any]:
    """``amoeba <args> -j`` on ``client`` in ``where``; the result document."""
    done = client.run_in(where, *args, "-j")
    assert done.code == expect, done.err + done.out
    document: dict[str, Any] = json.loads(done.out)
    return document


def members_seen_by(client: ClientHome, where: Path) -> dict[str, dict[str, Any]]:
    listed = run(client, where, "list", "members")
    return {row["name"]: row for row in listed["members"]}


def _shared(hub: FixtureHub) -> tuple[tuple[ClientHome, Path], tuple[ClientHome, Path]]:
    """The one repo as each machine has it: SSH on alpha, HTTPS on beta."""
    alpha, beta = hub.clients[FIRST], hub.clients[SECOND]
    return (
        (alpha, alpha.clone("shared", SSH_ORIGIN, "cf-shared-a", NAME)),
        (beta, beta.clone("shared", HTTPS_ORIGIN, "cf-shared-b", NAME)),
    )


@pytest.mark.parametrize("rename_between", [False, True], ids=["plain", "renamed"])
def test_add_on_both_machines_gives_one_member_with_two_checkouts(
    hub: FixtureHub, rename_between: bool
) -> None:
    (alpha, on_alpha), (beta, on_beta) = _shared(hub)

    first = run(alpha, on_alpha, "add")
    name = NAME
    if rename_between:
        name = "renamed-repo"
        renamed = run(alpha, on_alpha, "add", "--name", name)
        assert renamed["outcome"] == "applied"
    second = run(beta, on_beta, "add")

    assert first["outcome"] == second["outcome"] == "applied"
    for client, where in ((alpha, on_alpha), (beta, on_beta)):
        seen = members_seen_by(client, where)
        assert list(seen) == [name]
        row = seen[name]
        assert row["origin"] == REDUCED
        assert sorted(c["machine"] for c in row["checkouts"]) == [FIRST, SECOND]
        by_machine = {c["machine"]: c for c in row["checkouts"]}
        assert by_machine[FIRST]["cf_project_id"] == "cf-shared-a"
        assert by_machine[SECOND]["cf_project_id"] == "cf-shared-b"
        assert by_machine[FIRST]["path"] == str(on_alpha)
        assert by_machine[SECOND]["path"] == str(on_beta)


def test_the_recorded_origin_keeps_a_port(hub: FixtureHub) -> None:
    alpha = hub.clients[FIRST]
    repo = alpha.clone("ported", "https://git.example:8443/Org/Ported.git", "cf-p")

    run(alpha, repo, "add")

    assert members_seen_by(alpha, repo)["ported"]["origin"] == (
        "git.example:8443/org/ported"
    )


def test_another_repo_under_a_taken_name_is_name_taken_then_name_creates_it(
    hub: FixtureHub,
) -> None:
    (alpha, on_alpha), (beta, _) = _shared(hub)
    run(alpha, on_alpha, "add")
    other = beta.clone("other", "https://github.com/org/other", "cf-other", NAME)

    refused = run(beta, other, "add", expect=1)
    created = run(beta, other, "add", "--name", "other-repo")

    (problem,) = refused["problems"]
    assert problem["code"] == "name_taken"
    assert REDUCED in problem["detail"]
    assert "github.com/org/other" in problem["detail"]
    assert created["outcome"] == "applied"
    assert set(members_seen_by(beta, other)) == {NAME, "other-repo"}


def test_a_second_checkout_with_no_origin_is_no_origin(hub: FixtureHub) -> None:
    alpha, beta = hub.clients[FIRST], hub.clients[SECOND]
    first = alpha.clone("bare", None, "cf-bare-a", "bare-repo")
    second = beta.clone("bare", None, "cf-bare-b", "bare-repo")
    run(alpha, first, "add")

    refused = run(beta, second, "add", expect=1)

    (problem,) = refused["problems"]
    assert problem["code"] == "no_origin"
    assert members_seen_by(beta, second)["bare-repo"]["checkouts"][0]["machine"] == (
        FIRST
    )


def test_add_project_with_a_wake_command_is_refused_from_either_machine(
    hub: FixtureHub,
) -> None:
    (alpha, on_alpha), (beta, on_beta) = _shared(hub)
    run(alpha, on_alpha, "add")

    for client, where in ((alpha, on_alpha), (beta, on_beta)):
        refused = run(
            client,
            where,
            "add",
            "--project",
            NAME,
            "--wake-command",
            "claude -p go",
            expect=1,
        )
        (problem,) = refused["problems"]
        assert problem["code"] == "malformed"


def _direct_call(
    client: ClientHome,
    name: str,
    document: object,
    extra: Mapping[str, object] | None,
) -> None:
    """260's client call, made directly with a body the CLI would never build."""
    layout = hub_layout(client.home)
    client_file = load_client_file(layout.client_file, layout.pinned_cert)
    call(client_file, layout.pinned_cert, name, document, extra=extra)


def _last_called(hub: FixtureHub, machine: str) -> str | None:
    done = hub.run_in(hub.home, "hub", "machines", "-j")
    assert done.code == 0, done.err
    rows: list[dict[str, Any]] = json.loads(done.out)
    return next(row["last_called_at"] for row in rows if row["name"] == machine)


def test_a_body_with_an_unreduced_origin_is_malformed_and_writes_nothing(
    hub: FixtureHub,
) -> None:
    (alpha, on_alpha), _ = _shared(hub)
    unreduced = {
        "project_id": "cf-x",
        "name": NAME,
        "path": str(on_alpha),
        "origin": "https://user:hunter2@github.com/org/shared-repo.git",
    }

    with pytest.raises(HubRefusedError) as raised:
        _direct_call(alpha, "add", {}, {"here": unreduced})

    assert raised.value.code is RefusalCode.MALFORMED_CALL
    assert "hunter2" not in str(raised.value)
    assert members_seen_by(alpha, on_alpha) == {}


def test_a_call_lacking_here_or_runs_is_malformed_with_the_touch_committed(
    hub: FixtureHub,
) -> None:
    (alpha, on_alpha), _ = _shared(hub)
    before = _last_called(hub, FIRST)

    for name, extra in (("add", None), ("status", {"here": {"project_id": "x"}})):
        with pytest.raises(HubRefusedError) as raised:
            _direct_call(alpha, name, {}, extra)
        assert raised.value.code is RefusalCode.MALFORMED_CALL

    assert _last_called(hub, FIRST) != before
    assert members_seen_by(alpha, on_alpha) == {}


def test_members_rm_and_add_project_send_no_here_and_make_no_cf_call(
    hub: FixtureHub, tmp_path: Path
) -> None:
    (alpha, on_alpha), (beta, on_beta) = _shared(hub)
    run(alpha, on_alpha, "add")
    run(beta, on_beta, "add")
    nowhere = tmp_path / "not-a-project"
    nowhere.mkdir()
    calls_before = alpha.cf_calls()

    listed = run(alpha, nowhere, "list", "members")
    added = run(alpha, nowhere, "add", "--project", NAME, "--name", "better-name")
    removed_checkout = run(alpha, nowhere, "rm", "--checkout", str(on_alpha))
    removed = run(alpha, nowhere, "rm", "better-name")

    assert [row["name"] for row in listed["members"]] == [NAME]
    assert added["working_directory"] is None
    assert removed_checkout["outcome"] == "applied"
    assert removed["outcome"] == "applied"
    assert removed["working_directory"] is None
    assert alpha.cf_calls() == calls_before, "a command asked cf with nothing to ask"


def test_two_worktrees_and_the_other_machines_clone_read_one_request(
    hub: FixtureHub,
) -> None:
    (alpha, on_alpha), (beta, on_beta) = _shared(hub)
    tree = alpha.worktree(on_alpha, "shared-tree")
    sender = beta.clone("sender", "https://github.com/org/sender", "cf-sender")
    run(alpha, on_alpha, "add")
    run(beta, on_beta, "add")
    run(beta, sender, "add")
    sent = run(
        beta, sender, "send", "--id", "ask-1", "--to", NAME, "--subject", "s",
        "--body", "b",
    )  # fmt: skip
    assert sent["outcome"] == "sent"

    seen = [
        run(alpha, on_alpha, "inbox"),
        run(alpha, tree, "inbox"),
        run(beta, on_beta, "inbox"),
    ]

    for inbox in seen:
        assert [r["id"] for r in inbox["requests"]] == ["ask-1"]
    first = run(alpha, on_alpha, "reply", "ask-1", "accept")
    second = run(beta, on_beta, "reply", "ask-1", "accept", expect=1)
    assert first["request"]["state"] == "accepted"
    assert second["outcome"] == "rejected"


def test_status_and_list_show_the_clients_runs_under_the_right_members(
    hub: FixtureHub,
) -> None:
    (alpha, on_alpha), (beta, on_beta) = _shared(hub)
    run(alpha, on_alpha, "add")
    run(beta, on_beta, "add")
    alpha.set_runs(
        [
            {
                "run_id": "alpha-run",
                "pipeline": "p",
                "status": "running",
                "working_directory": str(on_alpha),
                "checkpoint": None,
            }
        ]
    )

    for command in ("status", "list"):
        on_a = run(alpha, on_alpha, command)
        member = on_a["programs"][0]["members"][0]
        assert member["member"]["name"] == NAME
        assert [r["run_id"] for r in member["runs"]] == ["alpha-run"]
        on_b = run(beta, on_beta, command)
        assert on_b["programs"][0]["members"][0]["runs"] == []


SECRET = "s3cret-password"


def _files_under(root: Path, skip: tuple[Path, ...] = ()) -> Iterator[Path]:
    for path in sorted(root.rglob("*")):
        if path.is_file() and not any(path.is_relative_to(s) for s in skip):
            yield path


def test_a_raw_origin_with_a_password_is_in_no_output_log_or_store_byte(
    hub: FixtureHub,
) -> None:
    alpha = hub.clients[FIRST]
    repo = alpha.clone(
        "pw", f"https://user:{SECRET}@github.com/org/pw-repo.git", "cf-pw"
    )
    outputs: list[str] = []
    for args in (("add",), ("list", "members"), ("status",), ("add", "--name", "pw2")):
        done = alpha.run_in(repo, *args, "-j")
        assert done.code == 0, done.err
        outputs += [done.out, done.err]

    seen = members_seen_by(alpha, repo)
    assert list(seen) == ["pw2"]
    assert seen["pw2"]["origin"] == "github.com/org/pw-repo"
    assert not any(SECRET in text for text in outputs)
    # The repo's own .git/config holds the address git printed, nothing of Amoeba's.
    leaked = [
        path
        for home in (hub.home, alpha.home)
        for path in _files_under(home, skip=(alpha.home / "repos",))
        if SECRET.encode() in path.read_bytes()
    ]
    assert leaked == []
    assert not any(SECRET in line for line in hub.stderr_lines + hub.stdout_lines)


def test_a_hub_on_a_schema_11_store_names_each_member_by_its_id_and_they_work(
    tmp_path: Path,
) -> None:
    hub = FixtureHub(tmp_path)
    build_schema_11_store(
        hub.layout.store_path, [OldMember("old-forge"), OldMember("old-guide")]
    )
    try:
        hub.start()
        alpha = hub.join(FIRST)
        repo = alpha.clone("forge", "https://github.com/org/forge", "cf-forge", "forge")
        listed = members_seen_by(alpha, repo)
        assert set(listed) == {"old-forge", "old-guide"}
        assert all(row["checkouts"] == [] for row in listed.values())

        renamed = run(alpha, repo, "add", "--project", "old-forge", "--name", "forge")
        attached = run(alpha, repo, "add", "--attach-to", "old-guide")
        removed = run(alpha, repo, "rm", "old-forge")
        remaining = members_seen_by(alpha, repo)
    finally:
        hub.close()

    assert renamed["outcome"] == attached["outcome"] == "applied"
    assert removed["outcome"] == "applied"
    assert list(remaining) == ["old-guide"]
    (checkout,) = remaining["old-guide"]["checkouts"]
    assert checkout["path"] == str(repo)


def test_add_and_rm_text_needs_no_config_on_a_joined_machine(hub: FixtureHub) -> None:
    """The text of ``add`` and ``rm`` read the local config's default rules, but a
    joined machine's config is not the one that applies (the hub's is) and may not
    exist: the change was already applied on the hub, so the text says ``default``
    alone and the command succeeds (found running the walkthrough)."""
    (alpha, on_alpha), _ = _shared(hub)
    assert not (alpha.home / "config.yaml").exists()

    added = alpha.run_in(on_alpha, "add")
    removed = alpha.run_in(on_alpha, "rm", NAME)

    assert added.code == 0, added.err
    assert f"added member {NAME}" in added.out
    assert "rules: default\n" in added.out
    assert removed.code == 0, removed.err
