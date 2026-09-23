#!/usr/bin/env python3
"""Seed one node blocked on a human in the ``demo`` project.

Why this script exists: nothing outside the resident process can create a node
until initiative 120 — the inbox's three submission kinds create projects,
resolve blocks, and record intents, but none of them makes a node. The slice
103 verification walkthrough needs a human-blocked node to resolve, so this
script makes one.

It opens the store **read-write**, so it runs only while the resident process
is stopped. That is enforced, not asked for: the script takes the instance
lock for as long as it writes and refuses if the process holds it.
``tests/test_writer_guard.py`` names this script in its allow-list for that
reason.

Blocking a node on a human writes its escalation message in the same
transaction (D3), so after this runs, ``amoeba inspect messages --project demo
--channel escalation`` shows the row, and the printed blocked-state id is what
``amoeba submit resolution --blocked-state-id`` takes.

    export AMOEBA_STORE_DIR="$(mktemp -d)"
    uv run amoeba submit create-project --project demo --by operator
    uv run python scripts/demo_inbox.py
"""

from __future__ import annotations

import argparse
import sys

from amoeba.process.instance_lock import InstanceLock
from amoeba.store import BlockedKind, NodeKind, Store, paths

PROJECT = "demo"


def main(argv: list[str] | None = None) -> int:
    """Seed the node, print its id and its blocked-state id."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--context",
        default="Approve the plan before the slice proceeds.",
        help="What the human is asked to decide.",
    )
    args = parser.parse_args(argv)

    with InstanceLock() as lock:
        if not lock.acquired:
            raise SystemExit(
                f"the resident process holds {lock.path}; run 'amoeba stop' first"
            )
        with Store.open(project_id=PROJECT) as store:
            node = store.create_node(
                project_id=PROJECT, kind=NodeKind.SLICE, title="awaiting a human"
            )
            blocked = store.block(node.id, kind=BlockedKind.HUMAN, context=args.context)

    print(f"store dir:         {paths.store_dir()}")
    print(f"node id:           {node.id}")
    print(f"blocked state id:  {blocked.id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
