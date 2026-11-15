"""One process of the message load test, started together with its siblings.

Usage: ``messages_worker.py <store path> <gate directory> <mode> <number>``.

* ``mixed``: ``send`` request ``req-<number>`` to the shared recipient, ``accept`` it
  as the recipient, then read the recipient's ``inbox`` twice (without ``since``, and
  from 0).
* ``shared``: ``accept`` the one request every ``shared`` worker races for.

The worker marks itself ready, waits for the parent to create ``go``, runs, and prints
one JSON line with each call's operation, outcome, rejection and wall time (``busy``
if the store stayed locked past its timeout).
"""

from __future__ import annotations

import json
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from cf_fixtures import OUTSIDE_ANY_PROJECT
from operations.message_support import (
    CONFIG,
    RECIPIENT_NAME,
    message_cf,
    message_deps,
    send_request_as_sender,
)
from operations.release_support import SettableClock
from operations.set_up_support import DIRECTORY

from amoeba.operations.deps import Deps
from amoeba.operations.inbox import inbox
from amoeba.operations.reply import reply
from amoeba.store.errors import StoreBusyError
from amoeba.store.store import Store

GATE_FILE = "go"
GATE_POLL_SECONDS = 0.002
GATE_TIMEOUT_SECONDS = 60.0
BUSY = "busy"
SHARED_REQUEST_ID = "shared"
MIXED = "mixed"
SHARED = "shared"


def _timed(operation: str, call: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    started = time.monotonic()
    try:
        record = call()
    except StoreBusyError:
        record = {"outcome": BUSY}
    return {"operation": operation, **record, "seconds": time.monotonic() - started}


def _accept(store: Store, deps: Deps, request_id: str) -> dict[str, Any]:
    document = {"id": request_id, "action": "accept", "member": RECIPIENT_NAME}
    result = reply(store, CONFIG, document, directory=DIRECTORY, deps=deps)
    return {
        "outcome": result.outcome.value,
        "rejection": None if result.rejection is None else result.rejection.value,
    }


def _inbox(store: Store, deps: Deps, since: int | None) -> dict[str, Any]:
    document: dict[str, Any] = {"member": RECIPIENT_NAME}
    if since is not None:
        document["since"] = since
    result = inbox(store, document, directory=DIRECTORY, deps=deps)
    return {
        "outcome": result.outcome.value,
        "as_of_seq": result.as_of_seq,
        "request_ids": [view.id for view in result.requests],
        "delivery_seqs": [item.seq for item in result.deliveries],
        "delivery_message_ids": [item.message_id for item in result.deliveries],
    }


def _send(store: Store, deps: Deps, request_id: str) -> dict[str, Any]:
    result = send_request_as_sender(store, deps, request_id)
    return {"outcome": result.outcome.value}


def _run(mode: str, number: str, store: Store, work: Path) -> list[dict[str, Any]]:
    sender = message_deps(work, SettableClock())
    addressee = message_deps(work, SettableClock(), message_cf(OUTSIDE_ANY_PROJECT))
    if mode == SHARED:
        return [_timed("accept", lambda: _accept(store, addressee, SHARED_REQUEST_ID))]
    own = f"req-{number}"
    return [
        _timed("send", lambda: _send(store, sender, own)),
        _timed("accept", lambda: _accept(store, addressee, own)),
        _timed("inbox", lambda: _inbox(store, addressee, None)),
        _timed("inbox", lambda: _inbox(store, addressee, 0)),
    ]


def main(arguments: list[str]) -> None:
    store_path, gate, mode, number = (
        Path(arguments[0]),
        Path(arguments[1]),
        arguments[2],
        arguments[3],
    )
    work = gate / f"work-{number}"
    work.mkdir()
    (gate / f"ready-{number}").touch()
    deadline = time.monotonic() + GATE_TIMEOUT_SECONDS
    while not (gate / GATE_FILE).exists():
        if time.monotonic() > deadline:
            raise TimeoutError("the parent never opened the gate")
        time.sleep(GATE_POLL_SECONDS)
    with Store.open(store_path) as store:
        print(json.dumps(_run(mode, number, store, work)))


if __name__ == "__main__":
    main(sys.argv[1:])
