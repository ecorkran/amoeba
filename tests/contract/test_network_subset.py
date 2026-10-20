"""The network path, end to end, across a kill of each process (slice 110, D2).

An intent is POSTed and its outcome polled until applied; the change arrives over
SSE. Then ``amoeba serve`` is killed with ``kill -9``, a POST is refused, the
server restarts, and the stream resumes from ``Last-Event-ID``. Then the resident
process is killed: a POST made while it is down is accepted and delivered once it
restarts, on a stream that never reconnected. The SSE ``seq`` list must equal a
local read of the whole feed: no gap, no repeat.
"""

from __future__ import annotations

import signal

import httpx2
import pytest

from amoeba.store import ChangeKind, SubmissionKind
from contract.harness import PAYLOAD_BODY, ProofHarness
from contract.network import HTTP_OK, REQUEST_TIMEOUT_SECONDS, ServeProcess, SseFollower
from contract.runner_tenant import INTENT_STEP, ProofStep
from contract.scenario import ALPHA

SETUP, DELIVERY, SERVE_KILL, SERVE_RESTART, RESIDENT_KILL, END = range(1, 7)

#: The submitter the bridge would be, over HTTP.
BRIDGE = "proof-bridge"

#: The documented HTTP status for an accepted submission.
ACCEPTED = 202


def _intent_body(submission_id: str) -> dict[str, object]:
    """A network submission: exactly the four keys the contract names."""
    return {
        "kind": SubmissionKind.INTENT.value,
        "submission_id": submission_id,
        "submitted_by": BRIDGE,
        "payload": {PAYLOAD_BODY: {INTENT_STEP: ProofStep.BUILD_TREE.value}},
    }


def _post(server: ServeProcess, body: dict[str, object]) -> httpx2.Response:
    return httpx2.post(
        f"{server.base_url}/v1/projects/{ALPHA}/submissions",
        json=body,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )


def _is_applied(server: ServeProcess, submission_id: str) -> bool:
    response = httpx2.get(
        f"{server.base_url}/v1/projects/{ALPHA}/submissions/{submission_id}",
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    return response.status_code == HTTP_OK and (response.json()["outcome"] == "applied")


def test_the_network_path_survives_a_kill_of_each_process(
    proof_harness: ProofHarness,
) -> None:
    h = proof_harness
    h.start(SETUP)
    server = ServeProcess(h)
    server.start(SETUP)

    # Create the project over the network, then wait for the store to exist.
    create: dict[str, object] = {
        "kind": SubmissionKind.CREATE_PROJECT.value,
        "submission_id": "remote-create",
        "submitted_by": BRIDGE,
        "payload": {},
    }
    assert _post(server, create).status_code == ACCEPTED
    h.wait_until(
        SETUP, "the project to be created", lambda: _is_applied(server, "remote-create")
    )

    follower = SseFollower(server.base_url, ALPHA)
    h.add_reader(follower)
    follower.connect()

    # Delivery: POST, poll the outcome, receive the change.
    assert _post(server, _intent_body("remote-1")).status_code == ACCEPTED
    h.wait_until(DELIVERY, "remote-1 to apply", lambda: _is_applied(server, "remote-1"))
    h.wait_until(
        DELIVERY,
        "message_posted over SSE",
        lambda: ChangeKind.MESSAGE_POSTED.value in follower.kinds,
    )

    # kill -9 of the server: a POST is refused, and the stream resumes.
    h.wait_until(
        SERVE_KILL,
        "the tree the intent builds",
        lambda: follower.kinds.count(ChangeKind.NODE_CREATED.value) >= 3,
    )
    follower.expect_drop()
    server.kill(SERVE_KILL)
    h.wait_until(SERVE_KILL, "the stream to end", lambda: follower.stream_ended)
    with pytest.raises(httpx2.TransportError):
        _post(server, _intent_body("remote-refused"))

    server.start(SERVE_RESTART)
    follower.connect(last_event_id=follower.seqs[-1])
    assert _post(server, _intent_body("remote-2")).status_code == ACCEPTED
    h.wait_until(
        SERVE_RESTART, "remote-2 to apply", lambda: _is_applied(server, "remote-2")
    )
    h.wait_until(
        SERVE_RESTART,
        "remote-2's tree over the resumed stream",
        lambda: follower.kinds.count(ChangeKind.NODE_CREATED.value) >= 6,
    )

    # kill -9 of the resident process: the POST is queued, then delivered.
    assert h.process.kill_and_wait() == -signal.SIGKILL
    assert _post(server, _intent_body("remote-3")).status_code == ACCEPTED
    with h.read(ALPHA) as store:
        assert store.submission("remote-3") is None, "applied with no process running"
    h.start(RESIDENT_KILL)
    h.wait_until(
        RESIDENT_KILL, "remote-3 to apply", lambda: _is_applied(server, "remote-3")
    )
    h.wait_until(
        RESIDENT_KILL,
        "remote-3's tree on the stream that never reconnected",
        lambda: follower.kinds.count(ChangeKind.NODE_CREATED.value) >= 9,
    )

    # End: what SSE delivered is exactly the feed, with no gap and no repeat.
    def caught_up() -> bool:
        with h.read(ALPHA) as store:
            return bool(follower.seqs) and follower.seqs[-1] == store.change_head(ALPHA)

    h.wait_until(END, "the stream to reach the head of the feed", caught_up)
    with h.read(ALPHA) as store:
        local = store.changes(ALPHA, after=0, limit=store.change_head(ALPHA))
    assert follower.seqs == [change.seq for change in local]
