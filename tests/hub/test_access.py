"""Access control on the real hub: tokens that end, and the door version
(slice 260, D6, D8, D16)."""

from __future__ import annotations

import http.client
import json
import ssl
from importlib.metadata import version
from pathlib import Path

import pytest
from hub_fixture import FIRST, SECOND, FixtureHub, two_machine_hub

from amoeba.client import call as call_module
from amoeba.client.call import call
from amoeba.client.client_file import ClientFile, load_client_file, write_client_file
from amoeba.client.errors import HubRefusedError
from amoeba.wire.protocol import DOCUMENT_KEY, RefusalCode, RefusedReply, parse_reply
from amoeba.wire.times import DOOR_VERSION, DoorTimes

SHORT = DoorTimes(
    connect_seconds=2.0, read_seconds=10.0, retry_seconds=1.0, retry_pause_seconds=0.2
)


def _hub_log(hub: FixtureHub) -> str:
    return hub.layout.hub_log.read_text(encoding="utf-8")


def _bad_token_error(hub: FixtureHub, who: str) -> str:
    done = hub.clients[who].run("decisions", "-j")
    assert done.code == 3, (done.out, done.err)
    assert "HubRefusedError" in done.err
    assert "bad_token" in done.err
    assert f"amoeba hub invite {who}" in done.err
    assert "amoeba join" in done.err
    return done.err


def test_no_token_a_bad_token_a_removed_and_a_reinvited_machines_token_are_refused(
    tmp_path: Path,
) -> None:
    with two_machine_hub(tmp_path) as hub:
        client_home = hub.clients[FIRST].home
        old_alpha_token = hub.tokens[FIRST]
        old_beta_token = hub.tokens[SECOND]

        # No token: a raw call with no Authorization header.
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_REQUIRED
        context.load_verify_locations(cafile=client_home / "pinned-hub-cert.pem")
        connection = http.client.HTTPSConnection("127.0.0.1", hub.port, context=context)
        body = json.dumps({DOCUMENT_KEY: {}}).encode("utf-8")
        connection.request(
            "POST",
            "/call/hello",
            body=body,
            headers={
                "Amoeba-Door-Version": str(DOOR_VERSION),
                "Amoeba-Client-Version": "test",
                "Amoeba-Call-Id": "no-token",
            },
        )
        reply = parse_reply(connection.getresponse().read())
        connection.close()
        assert isinstance(reply, RefusedReply) and reply.code is RefusalCode.BAD_TOKEN

        # A bad token: the client file holds one the hub never issued.
        layout_file = client_home / "client.yaml"
        pinned = client_home / "pinned-hub-cert.pem"
        good = load_client_file(layout_file, pinned)
        write_client_file(
            layout_file,
            ClientFile(
                address=good.address, machine=good.machine, token="never-issued"
            ),
        )
        _bad_token_error(hub, FIRST)
        write_client_file(layout_file, good)
        assert hub.clients[FIRST].run("decisions", "-j").code == 0

        # A removed machine's token.
        removed = hub.run_in(hub.home, "hub", "rm-machine", SECOND, "-j")
        assert removed.code == 0, removed.err
        _bad_token_error(hub, SECOND)

        # A re-invited machine's old token.
        hub.invite(FIRST)
        assert hub.tokens[FIRST] != old_alpha_token
        _bad_token_error(hub, FIRST)

        log = _hub_log(hub)
        assert log.count("code=bad_token") >= 4
        for secret in (
            old_alpha_token,
            old_beta_token,
            hub.tokens[FIRST],
            "never-issued",
        ):
            assert secret not in log


def test_a_client_with_another_door_version_gets_both_versions_and_the_machine_shows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with two_machine_hub(tmp_path) as hub:
        home = hub.clients[FIRST].home
        client = load_client_file(home / "client.yaml", home / "pinned-hub-cert.pem")
        monkeypatch.setattr(call_module, "DOOR_VERSION", DOOR_VERSION + 1)

        with pytest.raises(HubRefusedError) as raised:
            call(client, home / "pinned-hub-cert.pem", "decisions", {}, SHORT)

        assert raised.value.code is RefusalCode.DOOR_VERSION
        assert str(DOOR_VERSION) in str(raised.value)
        assert str(DOOR_VERSION + 1) in str(raised.value)
        assert "uv tool install --force amoeba-ai" in str(raised.value)
        monkeypatch.undo()

        machines = hub.run_in(hub.home, "hub", "machines", "-j")
        rows = {row["name"]: row for row in json.loads(machines.out)}
        assert rows[FIRST]["client_version"] == version("amoeba-ai")
        assert rows[FIRST]["last_called_at"] is not None
