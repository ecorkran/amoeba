"""Verdicts apply exactly once under concurrent submitters and repeated SIGKILLs.

The ``verdict`` effect writes one verdict row plus one observation row per
finding in a single transaction, on the same drained path as ``intent``.
Several submitter **processes** each send a few hundred verdicts, each carrying
``FINDINGS_PER_VERDICT`` findings, against a node seeded before the run, and
resubmit a fraction under the same id. Meanwhile ``amoeba start`` is
``SIGKILL``ed and restarted at random points (``load_harness.run_with_kills``).

Afterwards, per project: every reported id has exactly one submission record
and exactly one verdict, every verdict has exactly ``FINDINGS_PER_VERDICT``
observations (so no transaction landed half-applied or twice), and
``recorded_seq`` never repeats. ``new/``, ``quarantine/``, and ``failed/`` are
empty.

**The drain bound was measured first, then set at roughly twice the slowest
observation.** Measured 20260927 on the development machine (Darwin 25.5.0,
Python 3.13.7, SQLite 3.50.4), 5 runs, final drain after the tenth kill:

    backlog at drain start    1,473 – 1,583 files
    final drain, min          0.830 s
    final drain, max          0.867 s   (~1,800 files/s, each 5 findings)
    bound asserted            1.8   s
"""

from __future__ import annotations

import random
import textwrap
import time
from pathlib import Path

from load_harness import (
    launch_submitters,
    measured,
    run_with_kills,
    seed_project,
    submitter_output,
)

from amoeba.inbox import failed, quarantined
from amoeba.store import Store, SubmissionOutcome

SUBMITTERS = 4
VERDICTS_PER_SUBMITTER = 1000
FINDINGS_PER_VERDICT = 5
RESUBMIT_FRACTION = 0.1

#: Same floor and reasoning as ``test_inbox_concurrent.py``.
KILL_WINDOW_SECONDS = (0.15, 0.4)
TARGET_KILLS = 10
MINIMUM_KILLS = 3

#: Asserted bound on the final drain. See the module docstring.
DRAIN_BOUND_SECONDS = 1.8

RUN_TIMEOUT_SECONDS = 180.0

#: One submitter process. Arguments: supervisor dir, project, node id, count,
#: seed, resubmit fraction, findings per verdict. Prints every submission id
#: it was told succeeded, one per line.
SUBMITTER_SOURCE = textwrap.dedent(
    """
    import random, sys
    from pathlib import Path

    from amoeba.inbox import submit
    from amoeba.store import SubmissionKind

    supervisor, project, node_id = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
    count, seed, fraction, per_verdict = (
        int(sys.argv[4]), int(sys.argv[5]), float(sys.argv[6]), int(sys.argv[7]),
    )
    rng = random.Random(seed)

    for index in range(count):
        submission_id = f"{project}-verdict-{index}"
        payload = {
            "node_id": node_id, "verdict": "CONCERNS", "derivation": "stated",
            "fallback_used": None, "findings_parsed": True,
            "provider_failure": False, "review_type": "code", "model": "load",
            "upstream": "squadron", "upstream_version": "0.14.0",
            "source": "artifact_frontmatter",
            "findings": [
                {"severity": "concern", "summary": f"finding {index % 7}-{slot}",
                 "location": f"src/m{slot}.py:{index}"}
                for slot in range(per_verdict)
            ],
        }
        for _ in range(2 if rng.random() < fraction else 1):
            submit(project_id=project, kind=SubmissionKind.VERDICT, payload=payload,
                   submitted_by=project, submission_id=submission_id,
                   store_dir=supervisor)
        print(submission_id, flush=True)
    """
).strip()


def _seed(supervisor_dir: Path, project: str) -> str:
    """Create the project's store with one node; return the node's id."""
    with Store.open_read_only(seed_project(supervisor_dir, project)) as store:
        return store.nodes_for_project(project)[0].id


def _assert_exactly_once(
    supervisor_dir: Path, project: str, reported: set[str]
) -> None:
    with Store.open_read_only(supervisor_dir / f"{project}.sqlite3") as store:
        records = store.submissions(project)
        verdicts = store.verdicts(project)
        observation_counts = {v.id: len(store.observations(v.id)) for v in verdicts}

    record_ids = [record.id for record in records]
    verdict_ids = [verdict.id for verdict in verdicts]
    sequence = [verdict.recorded_seq for verdict in verdicts]

    assert len(record_ids) == len(set(record_ids)), f"{project}: a record repeats"
    assert set(record_ids) == reported, f"{project}: records differ from reported ids"
    assert all(record.outcome is SubmissionOutcome.APPLIED for record in records)
    assert len(verdict_ids) == len(set(verdict_ids)), f"{project}: a verdict repeats"
    assert set(verdict_ids) == reported, f"{project}: verdicts differ from reported"
    assert len(sequence) == len(set(sequence)), f"{project}: recorded_seq repeats"
    assert set(observation_counts.values()) == {FINDINGS_PER_VERDICT}, (
        f"{project}: a verdict's observations were not written exactly once"
    )


def test_concurrent_verdicts_across_kills_apply_exactly_once(
    tmp_path: Path, supervisor_dir: Path, runs_dir: Path
) -> None:
    projects = [f"project-{number}" for number in range(SUBMITTERS)]
    arguments = [
        [
            str(supervisor_dir),
            project,
            _seed(supervisor_dir, project),
            str(VERDICTS_PER_SUBMITTER),
            str(number),
            str(RESUBMIT_FRACTION),
            str(FINDINGS_PER_VERDICT),
        ]
        for number, project in enumerate(projects)
    ]
    submitters = launch_submitters(
        tmp_path, supervisor_dir, SUBMITTER_SOURCE, arguments
    )
    run = run_with_kills(
        supervisor_dir,
        ["--sq-runs-dir", str(runs_dir), "--idle-interval", "0.02"],
        submitters,
        rng=random.Random(20260927),
        kill_window=KILL_WINDOW_SECONDS,
        target_kills=TARGET_KILLS,
        deadline=time.monotonic() + RUN_TIMEOUT_SECONDS,
    )

    for number, submitter in enumerate(submitters):
        submitter.wait()
        stdout_file, stderr_file = submitter_output(tmp_path, number)
        assert submitter.returncode == 0, stderr_file.read_text()
        _assert_exactly_once(
            supervisor_dir, projects[number], set(stdout_file.read_text().split())
        )

    assert run.kills >= MINIMUM_KILLS, (
        f"only {run.kills} kills landed while submitters ran; raise "
        "VERDICTS_PER_SUBMITTER rather than shortening the kill window"
    )
    assert run.drain_seconds < DRAIN_BOUND_SECONDS, measured(
        f"final drain of {run.backlog} files", run.drain_seconds, DRAIN_BOUND_SECONDS
    )
    assert quarantined(supervisor_dir) == []
    assert failed(supervisor_dir) == []
    print(
        f"\n{SUBMITTERS} submitters x {VERDICTS_PER_SUBMITTER} verdicts "
        f"x {FINDINGS_PER_VERDICT} findings, {run.kills} kills, "
        f"final drain of {run.backlog} files in {run.drain_seconds:.3f}s"
    )
