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
"""

from __future__ import annotations

import random
import subprocess
import sys
import textwrap
import time
from pathlib import Path

from cli_harness import await_running, cli_environment, run_cli, start_background

from amoeba.cli.main import ExitCode
from amoeba.inbox import failed, pending, quarantined
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


def _output_files(tmp_path: Path, number: int) -> tuple[Path, Path]:
    return tmp_path / f"submitter-{number}.out", tmp_path / f"submitter-{number}.err"


def _launch_submitters(
    tmp_path: Path, supervisor_dir: Path
) -> list[subprocess.Popen[bytes]]:
    """Start every submitter, each writing its output to files.

    Files, not pipes: nothing reads a submitter's output until it has exited,
    and a pipe nobody drains blocks its writer once the buffer fills — which
    on macOS can be small — hanging the run.
    """
    script = tmp_path / "submitter.py"
    script.write_text(SUBMITTER_SOURCE, encoding="utf-8")
    submitters: list[subprocess.Popen[bytes]] = []
    for number in range(SUBMITTERS):
        stdout_file, stderr_file = _output_files(tmp_path, number)
        with stdout_file.open("wb") as stdout, stderr_file.open("wb") as stderr:
            submitters.append(
                subprocess.Popen(
                    [
                        sys.executable,
                        str(script),
                        str(supervisor_dir),
                        f"project-{number}",
                        str(INTENTS_PER_SUBMITTER),
                        str(number),
                        str(RESUBMIT_FRACTION),
                        str(CREATE_TIMEOUT_SECONDS),
                    ],
                    stdin=subprocess.DEVNULL,
                    stdout=stdout,
                    stderr=stderr,
                    env=cli_environment(supervisor_dir),
                )
            )
    return submitters


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
    rng = random.Random(20260923)
    start_arguments = ["--sq-runs-dir", str(runs_dir), "--idle-interval", "0.02"]
    deadline = time.monotonic() + RUN_TIMEOUT_SECONDS

    submitters = _launch_submitters(tmp_path, supervisor_dir)
    process = start_background(supervisor_dir, start_arguments)
    kills = 0
    try:
        while any(submitter.poll() is None for submitter in submitters) or (
            kills < TARGET_KILLS and pending(supervisor_dir)
        ):
            assert time.monotonic() < deadline, "the run never finished"
            time.sleep(rng.uniform(*KILL_WINDOW_SECONDS))
            process.kill_and_wait()
            process.cleanup()
            kills += 1
            process = start_background(supervisor_dir, start_arguments)

        drain_started = time.monotonic()
        backlog = len(pending(supervisor_dir))
        await_running(supervisor_dir)
        while pending(supervisor_dir):
            assert time.monotonic() < deadline, "the inbox never drained"
            time.sleep(0.02)
        drain_seconds = time.monotonic() - drain_started
        assert run_cli(["stop"], supervisor_dir).returncode == ExitCode.OK
    finally:
        process.cleanup()
        for submitter in submitters:
            if submitter.poll() is None:
                submitter.kill()

    for number, submitter in enumerate(submitters):
        submitter.wait()
        stdout_file, stderr_file = _output_files(tmp_path, number)
        assert submitter.returncode == 0, stderr_file.read_text()
        _assert_exactly_once(
            supervisor_dir, f"project-{number}", set(stdout_file.read_text().split())
        )

    assert kills >= MINIMUM_KILLS, (
        f"only {kills} kills landed while submitters ran; raise "
        "INTENTS_PER_SUBMITTER rather than shortening the kill window"
    )
    assert quarantined(supervisor_dir) == []
    assert failed(supervisor_dir) == []
    print(
        f"\n{SUBMITTERS} submitters x {INTENTS_PER_SUBMITTER} intents, "
        f"{kills} kills, final drain of {backlog} files in {drain_seconds:.3f}s"
    )
