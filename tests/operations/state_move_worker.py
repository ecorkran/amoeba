"""One ``prepare_state_home`` call in its own process, released by a gate file.

Usage: ``state_move_worker.py <legacy home> <state home> <gate directory> <number>``.
The worker marks itself ready, waits for ``go`` in the gate directory, runs the move
and prints one JSON line with the report.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from amoeba.config.home import STORE_FILE_NAME, StateLayout
from amoeba.operations.state_move import prepare_state_home

GATE_FILE = "go"
GATE_POLL_SECONDS = 0.002
GATE_TIMEOUT_SECONDS = 60.0


def main(arguments: list[str]) -> None:
    legacy, state, gate, number = (
        Path(arguments[0]),
        Path(arguments[1]),
        Path(arguments[2]),
        arguments[3],
    )
    (gate / f"ready-{number}").touch()
    deadline = time.monotonic() + GATE_TIMEOUT_SECONDS
    while not (gate / GATE_FILE).exists():
        if time.monotonic() > deadline:
            raise TimeoutError("the parent never opened the gate")
        time.sleep(GATE_POLL_SECONDS)
    layout = StateLayout(
        state_home=state,
        store_path=state / STORE_FILE_NAME,
        answering_dir=state / "answering",
        logs_dir=state / "logs",
        calls_log_dir=state / "logs" / "calls",
        legacy_home=legacy,
    )
    report = prepare_state_home(layout)
    print(json.dumps({"store_moved": report.store_moved}))


if __name__ == "__main__":
    main(sys.argv[1:])
