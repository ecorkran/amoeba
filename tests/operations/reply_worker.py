"""One ``reply accept`` in its own process, started together with its siblings.

Usage: ``reply_worker.py <store path> <gate directory> <request id> <number>``. The
worker marks itself ready, waits for the parent to create ``go`` in the gate
directory, then accepts the request as its addressee and prints one JSON line: the
outcome, the rejection code and the problems, or ``busy`` if the store stayed locked
past its timeout.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from cf_fixtures import OUTSIDE_ANY_PROJECT

from amoeba.operations.reply import reply
from amoeba.store.errors import StoreBusyError
from amoeba.store.store import Store
from operations.message_support import (
    CONFIG,
    RECIPIENT_NAME,
    message_cf,
    message_deps,
)
from operations.release_support import SettableClock
from operations.set_up_support import DIRECTORY

GATE_FILE = "go"
GATE_POLL_SECONDS = 0.002
GATE_TIMEOUT_SECONDS = 60.0
BUSY = "busy"


def main(arguments: list[str]) -> None:
    store_path, gate_directory, request_id, number = (
        Path(arguments[0]),
        Path(arguments[1]),
        arguments[2],
        arguments[3],
    )
    work_directory = gate_directory / f"work-{number}"
    work_directory.mkdir()
    deps = message_deps(
        work_directory, SettableClock(), message_cf(OUTSIDE_ANY_PROJECT)
    )
    (gate_directory / f"ready-{number}").touch()
    deadline = time.monotonic() + GATE_TIMEOUT_SECONDS
    while not (gate_directory / GATE_FILE).exists():
        if time.monotonic() > deadline:
            raise TimeoutError("the parent never opened the gate")
        time.sleep(GATE_POLL_SECONDS)
    document = {"id": request_id, "action": "accept", "member": RECIPIENT_NAME}
    try:
        with Store.open(store_path) as store:
            result = reply(store, CONFIG, document, directory=DIRECTORY, deps=deps)
    except StoreBusyError:
        print(json.dumps({"outcome": BUSY}))
        return
    print(
        json.dumps(
            {
                "outcome": result.outcome.value,
                "rejection": None
                if result.rejection is None
                else result.rejection.value,
                "problems": list(result.problems),
            }
        )
    )


if __name__ == "__main__":
    main(sys.argv[1:])
