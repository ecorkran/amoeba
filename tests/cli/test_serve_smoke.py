"""End to end through real processes: ``amoeba start``, ``amoeba serve``, a client.

Creates a project over HTTP, reads a listing, follows the feed from
``as_of_seq``, and submits an intent; the follower receives one
``message_posted``. Then the resident process stops with the follower open: the
stream stays up, reads are served, and a POST is accepted and applied on the
next start. ``kill -9`` survival is walkthrough step 5; the restart matrix is
slice 110's.
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import httpx2
from cli_harness import (
    BackgroundCli,
    await_condition,
    await_listening,
    cli_environment,
    free_port,
    start_running,
    start_serve,
    stop_running,
)
from serve_harness import SseEvent, sse_events

from amoeba.serve.settings import ServeSettings
from amoeba.serve.stream import CHANGE_EVENT
from amoeba.store.feed_models import ChangeKind
from amoeba.store.inbox_models import INTENT_BODY, INTENT_NODE_ID, SubmissionKind

PROJECT = "demo"
_DEMO_SCRIPT = Path(__file__).parents[2] / "scripts" / "demo_evidence.py"
#: A read waits past one default heartbeat, which the CLI cannot shorten.
_READ_TIMEOUT = ServeSettings().heartbeat_interval_seconds + 10.0


def _seed_node(supervisor: Path) -> str:
    """The walkthrough's seeding; the resident process must be stopped."""
    result = subprocess.run(
        [sys.executable, str(_DEMO_SCRIPT)],
        capture_output=True,
        text=True,
        env=cli_environment(supervisor),
        timeout=30,
        check=True,
    )
    return result.stdout.strip()


def _submission(
    kind: SubmissionKind, sid: str, payload: dict[str, object]
) -> dict[str, object]:
    return {
        "kind": kind.value,
        "submission_id": sid,
        "submitted_by": "smoke",
        "payload": payload,
    }


def _applied(client: httpx2.Client, sid: str) -> bool:
    response = client.get(f"/v1/projects/{PROJECT}/submissions/{sid}")
    return response.status_code == 200 and response.json()["outcome"] == "applied"


def _next_frame(events: Iterator[SseEvent]) -> SseEvent:
    return next(events)


def test_serve_end_to_end(tmp_path: Path) -> None:
    supervisor, runs = tmp_path / "supervisor", tmp_path / "runs"
    supervisor.mkdir()
    runs.mkdir()
    port = free_port()
    server = start_serve(supervisor, ["--port", str(port)])
    resident: BackgroundCli | None = None
    try:
        await_listening(port, server)
        with httpx2.Client(
            base_url=f"http://127.0.0.1:{port}", timeout=_READ_TIMEOUT
        ) as client:
            create = _submission(SubmissionKind.CREATE_PROJECT, "smoke-create", {})
            assert (
                client.post(
                    f"/v1/projects/{PROJECT}/submissions", json=create
                ).status_code
                == 202
            )

            resident = start_running(supervisor, runs)
            await_condition(
                lambda: _applied(client, "smoke-create"), "create_project applied"
            )
            stop_running(supervisor, resident)
            node_id = _seed_node(supervisor)
            resident = start_running(supervisor, runs)

            nodes = client.get("/v1/listings/nodes", params={"project": PROJECT}).json()
            assert [row["id"] for row in nodes["rows"]] == [node_id]

            feed = client.stream(
                "GET",
                f"/v1/projects/{PROJECT}/feed",
                params={"after": str(nodes["as_of_seq"])},
            )
            with feed as response:
                assert response.status_code == 200
                events = sse_events(response.iter_lines())
                intent = _submission(
                    SubmissionKind.INTENT,
                    "smoke-intent",
                    {INTENT_NODE_ID: node_id, INTENT_BODY: {"ask": "status"}},
                )
                assert (
                    client.post(
                        f"/v1/projects/{PROJECT}/submissions", json=intent
                    ).status_code
                    == 202
                )

                change = _next_frame(events)
                assert change.event == CHANGE_EVENT
                assert (
                    json.loads(change.data or "")["kind"]
                    == ChangeKind.MESSAGE_POSTED.value
                )

                # The resident process stops with the follower open.
                stop_running(supervisor, resident)
                resident = None
                assert (
                    _next_frame(events).comment == "keepalive"
                )  # still open, nothing new
                assert (
                    client.get(
                        "/v1/listings/nodes", params={"project": PROJECT}
                    ).status_code
                    == 200
                )
                queued = _submission(
                    SubmissionKind.INTENT,
                    "smoke-queued",
                    {INTENT_NODE_ID: node_id, INTENT_BODY: {"ask": "again"}},
                )
                assert (
                    client.post(
                        f"/v1/projects/{PROJECT}/submissions", json=queued
                    ).status_code
                    == 202
                )

                resident = start_running(supervisor, runs)
                resumed = next(e for e in events if e.comment is None)
                assert (
                    json.loads(resumed.data or "")["kind"]
                    == ChangeKind.MESSAGE_POSTED.value
                )
            assert _applied(client, "smoke-queued")
    finally:
        if resident is not None:
            stop_running(supervisor, resident)
        server.cleanup()
