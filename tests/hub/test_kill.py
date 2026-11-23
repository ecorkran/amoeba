"""A real kill between the commit and the reply (slice 260, D18)."""

from __future__ import annotations

import sqlite3
import threading
import time
from contextlib import closing
from pathlib import Path

from hub_fixture import FIRST, FixtureHub, two_machine_hub

from amoeba.client.call import call
from amoeba.client.client_file import load_client_file
from amoeba.wire.times import DoorTimes

CALL_ID = "kill-test-call"
RULING = "A ruling made while the hub is killed."
POLL_SECONDS = 0.005
WAIT_SECONDS = 30.0


def _kept(hub: FixtureHub) -> int:
    uri = f"{hub.layout.store_path.as_uri()}?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as connection:
        row = connection.execute(
            "SELECT COUNT(*) FROM call_results WHERE call_id = ?", (CALL_ID,)
        )
        return int(row.fetchone()[0])


def _standing_rows(hub: FixtureHub) -> int:
    with closing(sqlite3.connect(hub.layout.store_path)) as connection:
        row = connection.execute("SELECT COUNT(*) FROM standing_answers")
        return int(row.fetchone()[0])


def test_a_hub_killed_once_the_result_is_kept_returns_the_same_result_to_the_retry(
    tmp_path: Path,
) -> None:
    with two_machine_hub(tmp_path) as hub:
        home = hub.clients[FIRST].home
        client = load_client_file(home / "client.yaml", home / "pinned-hub-cert.pem")
        cert = home / "pinned-hub-cert.pem"
        outcome: list[object] = []
        failure: list[BaseException] = []

        def make_the_call() -> None:
            try:
                outcome.append(
                    call(
                        client,
                        cert,
                        "standing",
                        {"text": RULING},
                        DoorTimes(),
                        call_id=CALL_ID,
                    )
                )
            except BaseException as error:  # noqa: BLE001 - handed to the test thread
                failure.append(error)

        caller = threading.Thread(target=make_the_call)
        caller.start()
        deadline = time.monotonic() + WAIT_SECONDS
        while _kept(hub) == 0:
            assert time.monotonic() < deadline, "the call was never kept"
            time.sleep(POLL_SECONDS)
        hub.kill()
        hub.start()
        caller.join(WAIT_SECONDS)

        assert not caller.is_alive()
        assert not failure, failure
        (result,) = outcome
        assert isinstance(result, dict) and result["outcome"] == "given"
        repeat = call(client, cert, "standing", {"text": RULING}, call_id=CALL_ID)
        assert repeat == result
        assert _standing_rows(hub) == 1
