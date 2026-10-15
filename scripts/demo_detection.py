#!/usr/bin/env python3
"""Seed a slice node and a human-blocked node in ``demo``; print both ids.

Why this script exists: nothing outside the resident process can create a node
until initiative 120. The slice 106 verification walkthrough needs a slice node
for detected reviews to attach to (``cf.slice_name`` matching the captured 102
task reviews in ``tests/fixtures/sq_reviews/``) and a blocked node for a human
reply to resolve.

It opens the store **read-write**, so it runs only while the resident process
is stopped. That is enforced: the script takes the instance lock for as long as
it writes and refuses if the process holds it. It also refuses unless
``AMOEBA_STORE_DIR`` is set, so a demo never seeds the real supervisor store.
``tests/test_writer_guard.py`` names this script in its allow-list.

    export AMOEBA_STORE_DIR="$(mktemp -d)"
    uv run amoeba submit create-project --project demo --by pm
    read SLICE_NODE BLOCKED_NODE < <(uv run python scripts/demo_detection.py)
"""

from __future__ import annotations

import argparse
import os
import sys

from amoeba.process.instance_lock import InstanceLock
from amoeba.store import BlockedKind, CFReference, NodeKind, Store
from amoeba.store.paths import STORE_DIR_ENV_VAR

PROJECT = "demo"
#: The slice the captured 102 task-review fixtures name in their frontmatter.
SLICE_NAME = "resident-process-and-recovery"


def main(argv: list[str] | None = None) -> int:
    """Seed both nodes and print their ids on one line, slice node first."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)

    if not os.environ.get(STORE_DIR_ENV_VAR):
        raise SystemExit(f"set {STORE_DIR_ENV_VAR} to a scratch directory first")

    with InstanceLock() as lock:
        if not lock.acquired:
            raise SystemExit(
                f"the resident process holds {lock.path}; run 'amoeba stop' first"
            )
        with Store.open(project_id=PROJECT) as store:
            slice_node = store.create_node(
                project_id=PROJECT,
                kind=NodeKind.SLICE,
                title=SLICE_NAME,
                cf=CFReference(slice_name=SLICE_NAME),
            )
            blocked = store.create_node(
                project_id=PROJECT, kind=NodeKind.GATE, title="awaiting a decision"
            )
            store.block(blocked.id, kind=BlockedKind.HUMAN, context="decide")

    print(slice_node.id, blocked.id)
    return 0


if __name__ == "__main__":
    sys.exit(main())
