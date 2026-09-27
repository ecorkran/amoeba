#!/usr/bin/env python3
"""Seed one node in the ``demo`` project and print only its id.

Why this script exists: nothing outside the resident process can create a node
until initiative 120, and a ``verdict`` submission must name one. The slice 104
verification walkthrough reviews this node, so the script makes it.

It opens the store **read-write**, so it runs only while the resident process
is stopped. That is enforced, not asked for: the script takes the instance
lock for as long as it writes and refuses if the process holds it.
``tests/test_writer_guard.py`` names this script in its allow-list for that
reason.

The review payloads the walkthrough submits sit beside it, in
``scripts/demo_evidence/``. Their finding text is real, from the captured 102
task-review rounds in ``tests/fixtures/sq_reviews/``.

    export AMOEBA_STORE_DIR="$(mktemp -d)"
    uv run amoeba submit create-project --project demo --by pm
    NODE=$(uv run python scripts/demo_evidence.py)
"""

from __future__ import annotations

import argparse
import sys

from amoeba.process.instance_lock import InstanceLock
from amoeba.store import NodeKind, Store

PROJECT = "demo"


def main(argv: list[str] | None = None) -> int:
    """Seed the node and print its id, alone, for shell capture."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)

    with InstanceLock() as lock:
        if not lock.acquired:
            raise SystemExit(
                f"the resident process holds {lock.path}; run 'amoeba stop' first"
            )
        with Store.open(project_id=PROJECT) as store:
            node = store.create_node(
                project_id=PROJECT, kind=NodeKind.SLICE, title="under review"
            )

    print(node.id)
    return 0


if __name__ == "__main__":
    sys.exit(main())
