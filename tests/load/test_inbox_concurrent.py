"""Exactly-once under concurrent submitters and repeated SIGKILLs.

Several submitter **processes** each create a project through the inbox, wait
for it to apply (the documented contract for submitting into a new project),
then submit a few hundred intents — resubmitting a fraction under the same id,
as a retrying bridge would (D2). Meanwhile the real ``amoeba start`` is
``SIGKILL``ed and restarted at random points until every submitter finishes,
then left to drain.

Afterwards: every id a submitter was told succeeded has exactly one record and
exactly one intent message, no ``applied_seq`` repeats, the record set equals
the reported set exactly (so nothing unreported — a stray ``tmp/`` file — was
ever applied), and ``new/``, ``quarantine/``, and ``failed/`` are all empty.

**The drain bound was measured first, then set at roughly twice the slowest
observation**, per slice 102's rule, so a failure means a regression in kind —
a per-file store reopen, a rescan of ``new/`` per file — not machine variance.

Measured 20260923 on the development machine (Darwin 25.5.0, Python 3.13.7,
SQLite 3.50.4), 10 runs, final drain after the tenth kill:

    backlog at drain start    6,092 – 6,334 files
    final drain, min          2.945 s
    final drain, median       ~3.08 s
    final drain, max          3.196 s   (~2,000 files/s)
    bound asserted            6.5   s

The bound is on the drain of a backlog whose size depends on how far the
submitters outran the killed process; both are printed on every run, so a
bound that stops matching reality is visible rather than quietly tuned.
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
    submitter_output,
)

from amoeba.inbox import failed, quarantined
from amoeba.store import Channel, Store, SubmissionOutcome

SUBMITTERS = 4
INTENTS_PER_SUBMITTER = 2000
RESUBMIT_FRACTION = 0.1

#: How long the process runs between kills, in seconds. The floor sits above
#: the ~0.09 s start-to-ready measured in ``test_crash_loop.py``: a window
#: shorter than startup kills most restarts before they apply anything, and
#: the run starves rather than tests anything.
KILL_WINDOW_SECONDS = (0.15, 0.4)

#: Kills keep landing after the submitters finish, while the backlog is being
#: applied, until this many have landed or the inbox is empty. Without it,
#: nearly every file applies after the last kill — measured: ~8,000 of ~8,800
#: — and the kills land mostly on startup rather than mid-apply.
TARGET_KILLS = 10

#: The fewest kills that count as "at random points throughout". Asserted, so
#: a machine fast enough to outrun the kills fails loudly instead of passing
#: vacuously.
MINIMUM_KILLS = 3

#: Asserted bound on the final drain. See the module docstring for the
#: measurement it is based on.
DRAIN_BOUND_SECONDS = 6.5

#: How long a submitter may wait for its project's creation to apply.
CREATE_TIMEOUT_SECONDS = 60.0

#: How long the whole run may take before it is declared stuck.
RUN_TIMEOUT_SECONDS = 180.0

#: One submitter process. Arguments: supervisor dir, project, count, seed.
#: Prints every submission id it was told succeeded, one per line.
SUBMITTER_SOURCE = textwrap.dedent(
    """
    import random, sys, time
    from pathlib import Path

    from amoeba.inbox import submit
    from amoeba.store import Store, StoreError, SubmissionKind, SubmissionOutcome
    from amoeba.store.inbox_models import INTENT_BODY

    supervisor, project, count, seed, fraction, timeout = (
        Path(sys.argv[1]), sys.argv[2], int(sys.argv[3]), int(sys.argv[4]),
        float(sys.argv[5]), float(sys.argv[6]),
    )
    rng = random.Random(seed)

    created = submit(project_id=project, kind=SubmissionKind.CREATE_PROJECT,
                     payload={}, submitted_by=project, store_dir=supervisor)
    print(created, flush=True)

    # The contract: wait for the create to apply before submitting into it.
    store_file = supervisor / f"{project}.sqlite3"
    deadline = time.monotonic() + timeout
    while True:
        if store_file.is_file():
            try:
                with Store.open_read_only(store_file) as store:
                    record = store.submission(created)
                if record is not None and record.outcome is SubmissionOutcome.APPLIED:
                    break
            except StoreError:
                pass  # mid-creation, or the process was just killed: retry
        if time.monotonic() > deadline:
            sys.exit(f"{project}: creation never applied")
        time.sleep(0.02)

    for index in range(count):
        submission_id = f"{project}-intent-{index}"
        for _ in range(2 if rng.random() < fraction else 1):
            submit(project_id=project, kind=SubmissionKind.INTENT,
                   payload={INTENT_BODY: {"index": index}}, submitted_by=project,
                   submission_id=submission_id, store_dir=supervisor)
        print(submission_id, flush=True)
    """
).strip()


def _submitter_arguments(supervisor_dir: Path) -> list[list[str]]:
    return [
        [
            str(supervisor_dir),
            f"project-{number}",
            str(INTENTS_PER_SUBMITTER),
            str(number),
            str(RESUBMIT_FRACTION),
            str(CREATE_TIMEOUT_SECONDS),
        ]
        for number in range(SUBMITTERS)
    ]


def _assert_exactly_once(
    supervisor_dir: Path, project: str, reported: set[str]
) -> None:
    with Store.open_read_only(supervisor_dir / f"{project}.sqlite3") as store:
        records = store.submissions(project)
        intents = store.messages(project, channel=Channel.INTENT)

    record_ids = [record.id for record in records]
    sequence = [record.applied_seq for record in records]
    message_ids = [message.submission_id for message in intents]

    assert len(record_ids) == len(set(record_ids)), f"{project}: a record repeats"
    assert len(sequence) == len(set(sequence)), f"{project}: applied_seq repeats"
    assert set(record_ids) == reported, f"{project}: records differ from reported ids"
    assert all(record.outcome is SubmissionOutcome.APPLIED for record in records)
    assert len(message_ids) == len(set(message_ids)), f"{project}: a message repeats"
    assert set(message_ids) == reported - {records[0].id}, f"{project}: messages differ"


def test_concurrent_submitters_across_kills_apply_exactly_once(
    tmp_path: Path, supervisor_dir: Path, runs_dir: Path
) -> None:
    submitters = launch_submitters(
        tmp_path,
        supervisor_dir,
        SUBMITTER_SOURCE,
        _submitter_arguments(supervisor_dir),
    )
    run = run_with_kills(
        supervisor_dir,
        ["--sq-runs-dir", str(runs_dir), "--idle-interval", "0.02"],
        submitters,
        rng=random.Random(20260923),
        kill_window=KILL_WINDOW_SECONDS,
        target_kills=TARGET_KILLS,
        deadline=time.monotonic() + RUN_TIMEOUT_SECONDS,
    )

    for number, submitter in enumerate(submitters):
        submitter.wait()
        stdout_file, stderr_file = submitter_output(tmp_path, number)
        assert submitter.returncode == 0, stderr_file.read_text()
        _assert_exactly_once(
            supervisor_dir, f"project-{number}", set(stdout_file.read_text().split())
        )

    assert run.kills >= MINIMUM_KILLS, (
        f"only {run.kills} kills landed while submitters ran; raise "
        "INTENTS_PER_SUBMITTER rather than shortening the kill window"
    )
    assert run.drain_seconds < DRAIN_BOUND_SECONDS, measured(
        f"final drain of {run.backlog} files", run.drain_seconds, DRAIN_BOUND_SECONDS
    )
    assert quarantined(supervisor_dir) == []
    assert failed(supervisor_dir) == []
    print(
        f"\n{SUBMITTERS} submitters x {INTENTS_PER_SUBMITTER} intents, "
        f"{run.kills} kills, final drain of {run.backlog} files "
        f"in {run.drain_seconds:.3f}s"
    )
