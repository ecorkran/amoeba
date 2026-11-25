"""The hub's touch for a session's calls and the row a refused tick leaves
(slice 263, D6)."""

from __future__ import annotations

from pathlib import Path

import pytest
from store.decision_support import CORE
from store.seed import mark_wake_wanted
from store.wake_support import COMMAND, give_checkout_command

from amoeba.operations.here_document import HereCaller, HereNotAProject
from amoeba.operations.steps.models_session import SessionTickRequest
from amoeba.store.models import Session
from amoeba.store.sessions import upsert_session
from amoeba.wire.protocol import (
    HEADER_CLIENT_VERSION,
    HEADER_DOOR_VERSION,
    HEADER_SESSION_CLIENT,
    HEADER_SESSION_DIRECTORY,
    HEADER_SESSION_ID,
    HEADER_SESSION_PROJECT,
    WORK_REPLY_KEY,
    DoneReply,
    RefusalCode,
    RefusedReply,
)
from amoeba.wire.times import DOOR_VERSION
from hub.call_support import NOW, HubRig, build_rig, result_of

SESSION = "ab" * 16
OLD_VERSION = DOOR_VERSION - 1
MACHINE_VERSIONS = (
    "SELECT client_version, door_version FROM machines WHERE name = 'alpha'"
)
SESSION_ROWS = (
    "SELECT session_id, member_id, client, directory, client_version, door_version "
    "FROM sessions"
)


@pytest.fixture
def rig(tmp_path: Path) -> HubRig:
    return build_rig(tmp_path)


def _tick(here: HereCaller | HereNotAProject | None = None) -> dict[str, object]:
    request = SessionTickRequest(
        here=HereCaller(project_id=CORE) if here is None else here,
        session_id=SESSION,
        client="claude-code",
        directory="/work/core",
        last_seen=None,
        push_confirmed=False,
    )
    return request.model_dump(mode="json")


def _session_headers(**changes: str) -> dict[str, str]:
    headers = {
        HEADER_SESSION_ID: SESSION,
        HEADER_SESSION_PROJECT: CORE,
        HEADER_SESSION_CLIENT: "claude-code",
        HEADER_SESSION_DIRECTORY: "/work/core",
    }
    headers.update(changes)
    return headers


def _old(**changes: str) -> dict[str, str]:
    """The headers of a session on an older door version."""
    return {
        HEADER_DOOR_VERSION: str(OLD_VERSION),
        HEADER_CLIENT_VERSION: "0.1.0",
        **_session_headers(**changes),
    }


def _refused(rig: HubRig, headers: dict[str, str]) -> RefusedReply:
    parsed = result_of(rig.call("session_tick", _tick(), headers=headers))
    assert isinstance(parsed, RefusedReply)
    assert parsed.code is RefusalCode.DOOR_VERSION
    return parsed


def test_a_session_call_sets_the_time_only_and_another_call_sets_the_versions(
    rig: HubRig,
) -> None:
    rig.call("hello", {})
    versions = rig.rows(MACHINE_VERSIONS)
    rig.advance(seconds=30)

    rig.call(
        "session_end",
        {"session_id": SESSION},
        headers={HEADER_CLIENT_VERSION: "9.9.9", **_session_headers()},
    )
    after_session_call = rig.rows(MACHINE_VERSIONS)
    rig.call("hello", {}, headers={HEADER_CLIENT_VERSION: "7.7.7"})

    assert versions == [("0.2.3", DOOR_VERSION)]
    assert after_session_call == versions
    assert rig.rows(MACHINE_VERSIONS) == [("7.7.7", DOOR_VERSION)]
    machine = rig.machine("alpha-token-for-the-call-tests")
    assert machine is not None


def test_an_old_session_never_writes_old_versions_onto_an_upgraded_machine(
    rig: HubRig,
) -> None:
    rig.call("hello", {})

    _refused(rig, _old())

    assert rig.rows(MACHINE_VERSIONS) == [("0.2.3", DOOR_VERSION)]
    rig.call("hello", {})
    assert rig.rows(MACHINE_VERSIONS) == [("0.2.3", DOOR_VERSION)]


def test_a_refused_tick_makes_the_row_with_the_callers_versions_and_keeps_it(
    rig: HubRig,
) -> None:
    _refused(rig, _old())
    started = rig.rows("SELECT started_at, heartbeat_at FROM sessions")
    rig.advance(seconds=20)

    _refused(rig, _old())

    assert rig.rows(SESSION_ROWS) == [
        (SESSION, CORE, "claude-code", "/work/core", "0.1.0", OLD_VERSION)
    ]
    again = rig.rows("SELECT started_at, heartbeat_at FROM sessions")
    assert again[0][0] == started[0][0]
    assert again[0][1] != started[0][1]


def test_a_door_version_above_the_hubs_is_behind_the_same_way(rig: HubRig) -> None:
    _refused(rig, _old(**{HEADER_DOOR_VERSION: str(DOOR_VERSION + 1)}))

    (row,) = rig.rows(SESSION_ROWS)
    assert row[5] == DOOR_VERSION + 1


def test_the_refusal_body_is_the_same_with_and_without_the_session_headers(
    rig: HubRig,
) -> None:
    plain = {
        HEADER_DOOR_VERSION: str(OLD_VERSION),
        HEADER_CLIENT_VERSION: "0.1.0",
    }

    with_headers = _refused(rig, _old())
    without = _refused(rig, plain)

    assert with_headers == without


@pytest.mark.parametrize(
    "headers",
    [
        {HEADER_SESSION_ID: "not-a-session-id"},
        {HEADER_SESSION_CLIENT: "bad\x1bclient"},
        {HEADER_SESSION_DIRECTORY: "%FF%FE"},
        {HEADER_SESSION_DIRECTORY: ""},
        {HEADER_SESSION_PROJECT: "no-such-project"},
        {HEADER_DOOR_VERSION: "9\x1b[2J" + "9" * 200},
    ],
    ids=["id", "client", "directory", "empty-directory", "not-a-member", "door"],
)
def test_bad_headers_write_no_row_and_the_refusal_stands(
    rig: HubRig, headers: dict[str, str]
) -> None:
    _refused(rig, _old(**headers))

    assert rig.rows(SESSION_ROWS) == []


def test_a_tick_with_no_project_header_writes_no_row(rig: HubRig) -> None:
    sent = _old()
    del sent[HEADER_SESSION_PROJECT]

    _refused(rig, sent)

    assert rig.rows(SESSION_ROWS) == []


def test_a_session_id_of_another_machine_writes_no_row_and_the_refusal_stands(
    rig: HubRig,
) -> None:
    _refused(rig, _old())
    rig.call("hello", {}, token="beta-token-for-the-call-tests")

    reply = rig.call(
        "session_tick",
        _tick(),
        token="beta-token-for-the-call-tests",
        headers=_old(),
    )

    assert isinstance(result_of(reply), RefusedReply)
    assert len(rig.rows(SESSION_ROWS)) == 1


def test_a_door_version_header_that_does_not_parse_leaves_the_column_alone(
    rig: HubRig,
) -> None:
    rig.call("hello", {})

    rig.call("hello", {}, headers={HEADER_DOOR_VERSION: "9\x1b[2J" + "9" * 200})

    assert rig.rows(MACHINE_VERSIONS) == [("0.2.3", DOOR_VERSION)]


def test_the_session_steps_are_served_and_keep_no_result(rig: HubRig) -> None:
    ticked = result_of(rig.call("session_tick", _tick(), headers=_session_headers()))
    ended = result_of(
        rig.call("session_end", {"session_id": SESSION}, headers=_session_headers())
    )

    assert isinstance(ticked, DoneReply)
    assert isinstance(ended, DoneReply)
    assert rig.rows("SELECT COUNT(*) FROM call_results") == [(0,)]
    assert rig.rows("SELECT COUNT(*) FROM sessions") == [(0,)]


def _wake_due_for_core(rig: HubRig, session_version: int) -> None:
    with rig.open_store() as store:
        alpha = rig.machine("alpha-token-for-the-call-tests")
        assert alpha is not None
        store.act_as(alpha)
        with store.write() as transaction:
            give_checkout_command(transaction, CORE, COMMAND)
            mark_wake_wanted(transaction, CORE, NOW)
            upsert_session(
                transaction,
                Session(
                    session_id=SESSION,
                    member_id=CORE,
                    client="claude-code",
                    directory="/work/core",
                    started_at=NOW,
                    heartbeat_at=NOW,
                    push_confirmed_at=NOW,
                    client_version="0.2.3",
                    door_version=session_version,
                ),
            )


def _work_flag(rig: HubRig) -> object:
    reply = result_of(rig.call("open_runs", {}))
    assert isinstance(reply, DoneReply)
    return reply.result[WORK_REPLY_KEY]


@pytest.mark.parametrize(
    ("served", "session", "held_off"),
    [
        (DOOR_VERSION, DOOR_VERSION, True),
        (DOOR_VERSION, DOOR_VERSION + 1, False),
        (DOOR_VERSION + 1, DOOR_VERSION + 1, True),
        (DOOR_VERSION + 1, DOOR_VERSION, False),
    ],
)
def test_a_wake_is_held_off_only_for_a_session_on_the_version_the_hub_serves(
    rig: HubRig, served: int, session: int, held_off: bool
) -> None:
    rig.door_version = served
    _wake_due_for_core(rig, session)

    assert _work_flag(rig) is (not held_off)
