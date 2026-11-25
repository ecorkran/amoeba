"""A session on another door version than the hub's, seen from an up-to-date machine
(slice 263, 8.3, D6, D12): the refusal names both versions, the row is behind in
``status`` and ``list`` and under **Behind the hub**, a behind session does not hold
off a wake, and an old session never makes its upgraded machine look behind.

A hub "one version up" is a client one version down: the hub serves ``DOOR_VERSION``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from store.decision_support import CORE
from user_configs import user_config

from amoeba.cli.render.waiting import render_waiting
from amoeba.operations.here_document import HereCaller
from amoeba.operations.runs_document import RunsDocument, runs_to_document
from amoeba.operations.status_models import StatusResult
from amoeba.operations.steps.models_session import SessionTickRequest
from amoeba.store.sessions import live_member_ids
from amoeba.wire.protocol import (
    HEADER_CLIENT_VERSION,
    HEADER_DOOR_VERSION,
    HEADER_SESSION_CLIENT,
    HEADER_SESSION_DIRECTORY,
    HEADER_SESSION_ID,
    HEADER_SESSION_PROJECT,
    DoneReply,
    RefusalCode,
    RefusedReply,
)
from amoeba.wire.times import DOOR_VERSION
from hub.call_support import BETA_TOKEN, NOW, HubRig, build_rig, result_of

OLD = DOOR_VERSION - 1
AHEAD = DOOR_VERSION + 1
STALE = user_config().session_stale_seconds
FIRST_SESSION = "ab" * 16
SECOND_SESSION = "cd" * 16


@pytest.fixture
def rig(tmp_path: Path) -> HubRig:
    return build_rig(tmp_path)


def _headers(session: str, door: int, client_version: str = "0.1.0") -> dict[str, str]:
    return {
        HEADER_DOOR_VERSION: str(door),
        HEADER_CLIENT_VERSION: client_version,
        HEADER_SESSION_ID: session,
        HEADER_SESSION_PROJECT: CORE,
        HEADER_SESSION_CLIENT: "claude-code",
        HEADER_SESSION_DIRECTORY: "/work/core",
    }


def _tick(rig: HubRig, session: str, door: int) -> RefusedReply:
    request = SessionTickRequest(
        here=HereCaller(project_id=CORE),
        session_id=session,
        client="claude-code",
        directory="/work/core",
        last_seen=None,
        push_confirmed=False,
    )
    parsed = result_of(
        rig.call(
            "session_tick",
            request.model_dump(mode="json"),
            headers=_headers(session, door),
        )
    )
    assert isinstance(parsed, RefusedReply), parsed
    assert parsed.code is RefusalCode.DOOR_VERSION
    return parsed


def _status(
    rig: HubRig, token: str | None = None, call_id: str = "s-1"
) -> StatusResult:
    extra: dict[str, object] = {
        "here": HereCaller(project_id=CORE).model_dump(),
        "runs": runs_to_document(RunsDocument()),
    }
    reply = rig.call("status", {}, call_id=call_id, extra=extra, **_token(token))
    parsed = result_of(reply)
    assert isinstance(parsed, DoneReply), parsed
    return StatusResult.model_validate(
        {k: v for k, v in parsed.result.items() if k in StatusResult.model_fields}
    )


def _token(token: str | None) -> dict[str, Any]:
    return {} if token is None else {"token": token}


def _sessions(result: StatusResult) -> list[Any]:
    return [
        session
        for program in result.programs
        for member in program.members
        for session in member.sessions
    ]


def test_the_refusal_names_both_versions(rig: HubRig) -> None:
    refused = _tick(rig, FIRST_SESSION, OLD)

    assert str(OLD) in refused.message
    assert str(DOOR_VERSION) in refused.message


def test_an_old_session_is_behind_in_status_and_in_the_section_and_so_is_a_later_one(
    rig: HubRig,
) -> None:
    _tick(rig, FIRST_SESSION, OLD)
    _tick(rig, SECOND_SESSION, OLD)

    result = _status(rig)

    sessions = _sessions(result)
    assert len(sessions) == 2
    assert all(s.behind and s.door_version == OLD for s in sessions)
    assert all(s.machine == "alpha" for s in sessions)
    text = render_waiting(result, now=NOW)
    assert "Behind the hub" in text
    assert f"door {OLD}" in text
    assert "uv tool install --force amoeba-ai" in text


def test_an_old_session_leaves_its_upgraded_machine_not_behind(rig: HubRig) -> None:
    _status(rig)
    _tick(rig, FIRST_SESSION, OLD)

    result = _status(rig, call_id="s-2")

    (alpha,) = [m for m in result.machines if m.name == "alpha"]
    assert alpha.door_version == DOOR_VERSION
    assert alpha.behind is False
    assert "Behind the hub\n  alpha  client" not in render_waiting(result, now=NOW)


def test_an_old_machine_is_listed_behind_after_a_call_of_its_own(rig: HubRig) -> None:
    refused = rig.call(
        "status",
        {},
        token=BETA_TOKEN,
        headers={HEADER_DOOR_VERSION: str(OLD), HEADER_CLIENT_VERSION: "0.1.0"},
    )
    assert isinstance(result_of(refused), RefusedReply)

    result = _status(rig)

    (beta,) = [m for m in result.machines if m.name == "beta"]
    assert (beta.door_version, beta.behind) == (OLD, True)
    text = render_waiting(result, now=NOW)
    assert "Behind the hub" in text
    assert f"beta  client 0.1.0, door {OLD}" in text


def test_a_behind_session_does_not_hold_off_a_wake(rig: HubRig) -> None:
    _tick(rig, FIRST_SESSION, OLD)
    with rig.open_store() as store:
        machine = rig.machine("alpha-token-for-the-call-tests")
        assert machine is not None
        store.act_as(machine)
        with store.write() as transaction:
            transaction.execute("UPDATE sessions SET push_confirmed_at = heartbeat_at")
        with store.read() as transaction:
            held = live_member_ids(
                transaction, rig.clock(), STALE, door_version=DOOR_VERSION
            )
            behind = live_member_ids(transaction, rig.clock(), STALE, door_version=OLD)
    assert held == frozenset()
    assert behind == frozenset({CORE})


def test_a_door_version_above_the_hubs_is_ahead_of_the_hub_with_no_client_command(
    rig: HubRig,
) -> None:
    _tick(rig, FIRST_SESSION, AHEAD)

    text = render_waiting(_status(rig), now=NOW)

    assert "Behind the hub" in text
    assert "ahead of the hub" in text
    assert "hub is the one to upgrade" in text
    assert "uv tool install" not in text
