"""The real hub app on a thread, for client tests over real TLS (slice 260, D18).

``uvicorn`` serves the Starlette app on ``127.0.0.1`` and a free port (no macOS
firewall prompt), with a certificate made by ``make_certificate`` and a throwaway hub
store. It can stop and start again on the same store and the same port.
"""

from __future__ import annotations

import asyncio
import socket
import threading
import time
from functools import partial
from pathlib import Path

import uvicorn

from amoeba.hub.app import create_app
from amoeba.hub.calls import DoorHooks, handle_call
from amoeba.hub.certificate import make_certificate
from amoeba.hub.serve import make_server
from amoeba.wire.times import DOOR_VERSION
from hub.call_support import HubRig, build_rig

LOOPBACK = "127.0.0.1"
START_TIMEOUT_SECONDS = 10.0
STOP_TIMEOUT_SECONDS = 10.0
POLL_SECONDS = 0.01


class InProcessHub:
    """A serving hub inside the test process."""

    def __init__(
        self,
        root: Path,
        hooks: DoorHooks = DoorHooks(),  # noqa: B008
        door_version: int = DOOR_VERSION,
    ) -> None:
        self.rig: HubRig = build_rig(root)
        self.hooks = hooks
        #: The door version this hub serves; a test restarts one a version up.
        self.door_version = door_version
        self.cert_path = self.rig.layout.hub_cert
        self.key_path = self.rig.layout.hub_key
        make_certificate(self.cert_path, self.key_path)
        self.port = 0
        self._server: uvicorn.Server | None = None
        self._thread: threading.Thread | None = None

    @property
    def address(self) -> str:
        return f"{LOOPBACK}:{self.port}"

    def start(self) -> None:
        """Serve; on a restart, on the port the first start picked."""
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind((LOOPBACK, self.port))
        self.port = listener.getsockname()[1]
        handle = partial(
            handle_call,
            open_store=self.rig.open_store,
            clock=self.rig.clock,
            # Read on each call, so a test may change the rig's config while serving.
            load_config=lambda: self.rig.config(),
            hooks=self.hooks,
            door_version=self.door_version,
        )
        server = make_server(
            create_app(handle, self.rig.clock, self.door_version),
            self.cert_path,
            self.key_path,
        )
        thread = threading.Thread(
            target=lambda: asyncio.run(server.serve(sockets=[listener])), daemon=True
        )
        thread.start()
        deadline = time.monotonic() + START_TIMEOUT_SECONDS
        while not server.started:
            if time.monotonic() > deadline or not thread.is_alive():
                raise TimeoutError("the in-process hub did not start")
            time.sleep(POLL_SECONDS)
        self._server, self._thread = server, thread

    def stop(self) -> None:
        if self._server is None or self._thread is None:
            return
        self._server.should_exit = True
        self._thread.join(STOP_TIMEOUT_SECONDS)
        self._server, self._thread = None, None

    def __enter__(self) -> InProcessHub:
        self.start()
        return self

    def __exit__(self, *_exc: object) -> None:
        self.stop()
