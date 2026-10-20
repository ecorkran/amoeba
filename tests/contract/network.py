"""The network subset's two moving parts: ``amoeba serve`` and an SSE follower.

Both are real. The server is a subprocess the harness can ``kill -9``; the
follower is a thread reading the feed over HTTP. The follower drops only at
points the test plans: any other end of the stream is a failure re-raised at the
harness's next wait.
"""

from __future__ import annotations

import json
import signal
import socket
import sys
import threading

import httpx2
from serve_harness import SseEvent, sse_events

from contract.harness import HarnessFailure, ProofHarness
from contract.launched import LaunchedProcess

SERVE_PREFIX = "serve"
LOOPBACK = "127.0.0.1"
#: The documented SSE event name for a change (network-contract.md).
CHANGE_EVENT = "change"
#: Each socket read waits at most this; a frame that never comes fails fast.
READ_TIMEOUT_SECONDS = 30.0
REQUEST_TIMEOUT_SECONDS = 10.0
#: The documented status of a stream or a read that succeeded.
HTTP_OK = 200
JOIN_TIMEOUT_SECONDS = 10.0

#: A response any live server gives; the status is irrelevant.
_PROBE_PATH = "/v1/projects/probe/submissions/probe"


def free_port() -> int:
    """A loopback port nothing is listening on right now."""
    with socket.socket() as probe:
        probe.bind((LOOPBACK, 0))
        return int(probe.getsockname()[1])


class ServeProcess:
    """``amoeba serve`` on loopback, started and ``kill -9``-ed on demand."""

    def __init__(self, harness: ProofHarness) -> None:
        self._harness = harness
        self.port = free_port()
        self.base_url = f"http://{LOOPBACK}:{self.port}"
        self._current: LaunchedProcess | None = None

    def start(self, step: int) -> None:
        """Launch the server and wait until it answers a request."""
        label = self._harness.next_label(SERVE_PREFIX)
        self._current = self._harness.track(
            LaunchedProcess(
                label,
                [
                    sys.executable,
                    "-m",
                    "amoeba.cli.main",
                    "serve",
                    "--host",
                    LOOPBACK,
                    "--port",
                    str(self.port),
                ],
                environment=self._harness.environment(),
                working_dir=self._harness.supervisor_dir,
                stderr_path=self._harness.stderr_path_for(label),
            )
        )
        self._harness.wait_until(step, "amoeba serve to answer", self._answers)

    def _answers(self) -> bool:
        assert self._current is not None
        try:
            httpx2.get(self.base_url + _PROBE_PATH, timeout=REQUEST_TIMEOUT_SECONDS)
        except httpx2.TransportError:
            if not self._current.host.is_running():
                raise HarnessFailure("amoeba serve exited before it answered") from None
            return False
        return True

    def kill(self, step: int) -> None:
        """``kill -9``, and confirm that is how it died."""
        assert self._current is not None
        self._current.host.signal(signal.SIGKILL)
        self._harness.wait_until(
            step, "amoeba serve to die", lambda: not self._current_running()
        )

    def _current_running(self) -> bool:
        assert self._current is not None
        return self._current.host.is_running()


class SseFollower:
    """A feed stream over HTTP on a thread, recording each change's ``seq``."""

    def __init__(self, base_url: str, project_id: str) -> None:
        self.name = f"{project_id} SSE follower"
        self.error: BaseException | None = None
        self.seqs: list[int] = []
        self.kinds: list[str] = []
        self._base_url = base_url
        self._path = f"/v1/projects/{project_id}/feed"
        self._planned_drop = threading.Event()
        self._threads: list[threading.Thread] = []

    def connect(self, last_event_id: int | None = None) -> None:
        """Open the stream, resuming after ``last_event_id`` when given."""
        self._planned_drop.clear()
        thread = threading.Thread(target=self._run, args=(last_event_id,), daemon=True)
        self._threads.append(thread)
        thread.start()

    def expect_drop(self) -> None:
        """The stream is about to end on purpose; that is not a failure."""
        self._planned_drop.set()

    @property
    def stream_ended(self) -> bool:
        return not self._threads[-1].is_alive()

    def _run(self, last_event_id: int | None) -> None:
        headers = {} if last_event_id is None else {"Last-Event-ID": str(last_event_id)}
        try:
            with (
                httpx2.Client(
                    base_url=self._base_url, timeout=READ_TIMEOUT_SECONDS
                ) as client,
                client.stream("GET", self._path, headers=headers) as response,
            ):
                if response.status_code != HTTP_OK:
                    raise HarnessFailure(f"the feed answered {response.status_code}")
                for event in sse_events(response.iter_lines()):
                    self._record(event)
            if not self._planned_drop.is_set():
                raise HarnessFailure("the stream ended without being asked to")
        except Exception as failure:  # noqa: BLE001
            # Thread boundary: any unplanned end (transport, a malformed frame,
            # a bad id) is stored and re-raised on the main thread at the next
            # wait; a planned one is the point of the test.
            if not self._planned_drop.is_set():
                self.error = failure

    def _record(self, event: SseEvent) -> None:
        if event.comment is not None:
            return
        if event.event != CHANGE_EVENT or event.id is None or event.data is None:
            raise HarnessFailure(f"unexpected frame {event!r}")
        self.seqs.append(int(event.id))
        self.kinds.append(str(json.loads(event.data)["kind"]))

    def close(self) -> None:
        self.expect_drop()
        for thread in self._threads:
            thread.join(timeout=JOIN_TIMEOUT_SECONDS)
