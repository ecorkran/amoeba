#!/usr/bin/env python3
"""Seed a ``demo`` project exercising all three Squadron recovery outcomes.

Creates three nodes, each with one unresolved ``sq_run`` journal entry, against
a scratch runs directory seeded with copies of **real** Squadron run files:

- one entry with exactly **one** matching run   → recovery adopts it
- one entry with **no** matching run            → recovery escalates
- one entry with **two** matching runs          → recovery escalates

Run it, then start the resident process against the same runs directory and
watch recovery reconcile all three. This is step 3 of the slice's verification
walkthrough.

Uses only the **public** store API — nothing here reaches into internals.

    export AMOEBA_STORE_DIR="$(mktemp -d)"
    uv run python scripts/demo_journal.py --runs-dir "$AMOEBA_STORE_DIR/runs"
    uv run amoeba start --sq-runs-dir "$AMOEBA_STORE_DIR/runs"
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from amoeba.store import CommandKind, NodeKind, Store, paths

PROJECT = "demo"

#: Real Squadron run files shipped as test fixtures. Copied rather than
#: invented, so the demo exercises the parser against the shape it meets in
#: production.
FIXTURES_DIR = Path(__file__).parent.parent / "tests" / "fixtures" / "sq_runs"

#: The fixture the single-match and two-match cases are built from.
SOURCE_RUN = "run-20260505-review-a697ad3d.json"


def _load_fixture() -> dict[str, object]:
    """Read the real run file this demo derives its scratch runs from."""
    source = FIXTURES_DIR / SOURCE_RUN
    if not source.exists():
        raise SystemExit(
            f"fixture {source} is missing; run this from a source checkout"
        )
    payload = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit(f"fixture {source} does not hold a JSON object")
    return {str(key): value for key, value in payload.items()}


def _write_run(runs_dir: Path, payload: dict[str, object], run_id: str) -> None:
    """Write one run file under a given run id, keeping every other field."""
    payload = dict(payload)
    payload["run_id"] = run_id
    (runs_dir / f"{run_id}.json").write_text(json.dumps(payload, indent=2))


def seed_runs_directory(runs_dir: Path) -> dict[str, str]:
    """Seed the scratch runs directory. Returns the pipeline used per case.

    Three pipelines, so each journal entry matches a known number of runs:
    one file for the adopt case, none for the zero case, two for the ambiguous
    case.
    """
    runs_dir.mkdir(parents=True, exist_ok=True)
    fixture = _load_fixture()

    # Started after the entries will be issued, so the clock-tolerance
    # condition passes rather than silently excluding every candidate.
    started_at = (datetime.now(UTC) + timedelta(seconds=1)).isoformat()
    fixture["started_at"] = started_at.replace("+00:00", "Z")

    one_match = dict(fixture, pipeline="demo-one")
    _write_run(runs_dir, one_match, "run-demo-one-00000001")

    ambiguous = dict(fixture, pipeline="demo-two")
    _write_run(runs_dir, ambiguous, "run-demo-two-00000001")
    _write_run(runs_dir, ambiguous, "run-demo-two-00000002")

    # Nothing is written for demo-none: that is the zero-candidate case.
    return {"one": "demo-one", "none": "demo-none", "two": "demo-two"}


def journaled_params(fixture: dict[str, object]) -> dict[str, object]:
    """The params to journal, as a strict **subset** of the run's own.

    Squadron persists the pipeline definition's defaults merged with the
    caller's overrides, so a journaled mapping is normally a subset of what
    ends up in the run file. Taking one real key from the fixture keeps this
    demo honest: journaling a key the run does not carry would match nothing,
    which is the mistake this line exists to avoid.
    """
    params = fixture.get("params")
    if not isinstance(params, dict):
        raise SystemExit("fixture params are not a mapping")
    typed: dict[str, object] = {str(key): value for key, value in params.items()}
    if not typed:
        raise SystemExit("fixture params are empty; pick a different fixture")
    first_key = sorted(typed)[0]
    return {first_key: typed[first_key]}


def seed_store(pipelines: dict[str, str], params: dict[str, object]) -> list[str]:
    """Create the demo project's nodes and issue one entry against each.

    Args:
        pipelines: Case name to the pipeline its entry journals.
        params: The journaled params, a subset of what the run files carry.

    Returns:
        The journal entry ids, in the order the cases are described above.
    """
    entry_ids: list[str] = []

    with Store.open(project_id=PROJECT) as store:
        for case, pipeline in pipelines.items():
            node = store.create_node(
                project_id=PROJECT,
                kind=NodeKind.SLICE,
                title=f"{case}-match demo node",
            )
            entry = store.journal_issue(
                node.id,
                kind=CommandKind.SQ_RUN,
                parameters={"pipeline": pipeline, "params": dict(params)},
            )
            entry_ids.append(entry.id)
            print(f"  {case:5s}  node={node.id}  entry={entry.id}")

    return entry_ids


def main(argv: list[str] | None = None) -> int:
    """Seed the demo project and its scratch runs directory."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--runs-dir",
        type=Path,
        required=True,
        help="Scratch Squadron runs directory to seed. Never the real one.",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Remove an existing demo store and runs directory first.",
    )
    args = parser.parse_args(argv)

    store_file = paths.store_path(PROJECT)

    if args.reset:
        store_file.unlink(missing_ok=True)
        if args.runs_dir.exists():
            shutil.rmtree(args.runs_dir)

    if store_file.exists():
        raise SystemExit(
            f"a demo store already exists at {store_file}; pass --reset to replace it"
        )

    print(f"store dir:  {paths.store_dir()}")
    print(f"runs dir:   {args.runs_dir}")
    print("seeding three unresolved sq_run entries:")

    pipelines = seed_runs_directory(args.runs_dir)
    seed_store(pipelines, journaled_params(_load_fixture()))

    print()
    print("Now run recovery against the same runs directory:")
    print(f"  uv run amoeba start --sq-runs-dir {args.runs_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
