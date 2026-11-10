"""One ``set_up`` call in its own process, started together with its siblings.

Usage: ``set_up_worker.py <store path> <gate directory> <number>``. The worker marks
itself ready, waits for the parent to create ``go`` in the gate directory, then adds
member ``number`` to program ``demo`` and prints one JSON line: the outcome, or
``busy`` if the store stayed locked past its timeout.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from amoeba.store.errors import StoreBusyError
from amoeba.store.store import Store
from operations.set_up_support import run_set_up

GATE_FILE = "go"
GATE_POLL_SECONDS = 0.002
GATE_TIMEOUT_SECONDS = 60.0
BUSY = "busy"


def main(arguments: list[str]) -> None:
    store_path, gate_directory, number = (
        Path(arguments[0]),
        Path(arguments[1]),
        arguments[2],
    )
    (gate_directory / f"ready-{number}").touch()
    deadline = time.monotonic() + GATE_TIMEOUT_SECONDS
    while not (gate_directory / GATE_FILE).exists():
        if time.monotonic() > deadline:
            raise TimeoutError("the parent never opened the gate")
        time.sleep(GATE_POLL_SECONDS)
    document = {
        "program": "demo",
        "members": [{"project": f"member-{number}", "rules_paths": ["CLAUDE.md"]}],
    }
    try:
        with Store.open(store_path) as store:
            result = run_set_up(
                store, document, projects=[(f"id-{number}", f"member-{number}")]
            )
    except StoreBusyError:
        print(json.dumps({"outcome": BUSY}))
        return
    print(json.dumps({"outcome": result.outcome.value}))


if __name__ == "__main__":
    main(sys.argv[1:])
