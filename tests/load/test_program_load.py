"""The program inbox and the tick's program read under load.

Case 1: several submitter **processes** concurrently ``submit_program()`` a few
hundred ``register_member`` bodies each — resubmitting a fraction under the same
id, as a retrying bridge would — while ``ProgramInboxTenant`` drains. Afterwards
every id a submitter was told succeeded has exactly one record, no
``applied_seq`` repeats, the record set equals the reported set exactly, and
``new/``, ``quarantine/`` and ``failed/`` are empty.

Case 2: many projects, each a member of the program store's program, tick under
the Runner. Every tick stays within its deadline, and the program read opens no
member store.

**Bounds were measured first, then set at roughly twice the slowest
observation** (the rule ``test_inbox_concurrent.py`` states), so a failure means
a regression in kind — a per-file store reopen, a per-member store open in the
tick — not machine variance.

Measured 20261105 on the development machine (Darwin 25.5.0, Python 3.13),
5 runs each:

    case 1: 4 submitters x 300 bodies (+10% resubmitted), drain in-process
        total drain, min / max    2.048 / 2.126 s
        bound asserted            4.5 s
    case 2: 30 projects, every one a program member, 5 ticks, no polls
        slowest tick, min / max   0.005 / 0.005 s
        bound asserted            0.05 s (10x: at 5 ms scheduling noise
                                  dominates a 2x bound; a member-store open
                                  per project would cost far more than this)
"""

from __future__ import annotations

import textwrap
import time
from datetime import UTC, datetime
from pathlib import Path

import pytest
from load_harness import launch_submitters, measured, submitter_output
from local_host_harness import LocalHost
from program_harness import member, program_payload, register_program
from runner.observe_support import TEST_AMOEBA_VERSION, FakeCf

from amoeba.inbox import failed, layout, quarantined, submit_program
from amoeba.process import ProcessSettings
from amoeba.process.program_inbox_tenant import ProgramInboxTenant
from amoeba.runner.launch import LAUNCH_LOGS_DIRNAME
from amoeba.runner.project_config import ProjectConfig, ProjectSettings
from amoeba.runner.tenant import RunnerTenant
from amoeba.store import (
    NodeKind,
    ProgramStore,
    ProgramSubmissionKind,
    Store,
    SubmissionOutcome,
)
from amoeba.store.paths import program_dir, program_store_path

PROGRAM_ID = "demo"
SUBMITTERS = 4
BODIES_PER_SUBMITTER = 300
RESUBMIT_FRACTION = 0.1
INBOX_BATCH_SIZE = 50

#: Asserted bound on the whole drain, from the module docstring's measurement.
DRAIN_BOUND_SECONDS = 4.5

#: How long the run may take before it is declared stuck.
RUN_TIMEOUT_SECONDS = 120.0

#: One submitter process. Arguments: supervisor dir, name, count, seed, fraction.
#: Prints every submission id it was told succeeded, one per line.
SUBMITTER_SOURCE = textwrap.dedent(
    """
    import random, sys
    from pathlib import Path

    from amoeba.inbox import submit_program
    from amoeba.store import ProgramSubmissionKind

    supervisor, name, count, seed, fraction = (
        Path(sys.argv[1]), sys.argv[2], int(sys.argv[3]), int(sys.argv[4]),
        float(sys.argv[5]),
    )
    rng = random.Random(seed)

    for index in range(count):
        submission_id = f"{name}-member-{index}"
        body = {
            "program_id": "demo",
            "member": {
                "project_id": f"{name}-{index}",
                "requests_initiative": 790,
                "consumed": "from_source",
                "overrides": {},
            },
        }
        for _ in range(2 if rng.random() < fraction else 1):
            submit_program(kind=ProgramSubmissionKind.REGISTER_MEMBER,
                           payload=body, submitted_by=name,
                           submission_id=submission_id, store_dir=supervisor)
        print(submission_id, flush=True)
    """
).strip()


def _inbox_is_empty(supervisor_dir: Path) -> bool:
    return not layout.submission_files(layout.new_dir(program_dir(supervisor_dir)))


def test_concurrent_submitters_apply_exactly_once(
    tmp_path: Path, supervisor_dir: Path
) -> None:
    host = LocalHost(supervisor_dir, ProcessSettings(inbox_batch_size=INBOX_BATCH_SIZE))
    tenant = ProgramInboxTenant(supervisor_dir)
    first = submit_program(
        kind=ProgramSubmissionKind.REGISTER_PROGRAM,
        payload=program_payload(
            program_id=PROGRAM_ID, concept_member="seed", members=[member("seed")]
        ),
        submitted_by="load",
        store_dir=supervisor_dir,
    )
    tenant.tick(host)  # the program exists before any member is registered

    arguments = [
        [
            str(supervisor_dir),
            f"s{number}",
            str(BODIES_PER_SUBMITTER),
            str(number),
            str(RESUBMIT_FRACTION),
        ]
        for number in range(SUBMITTERS)
    ]
    submitters = launch_submitters(
        tmp_path, supervisor_dir, SUBMITTER_SOURCE, arguments
    )
    started = time.monotonic()
    try:
        while any(s.poll() is None for s in submitters) or not _inbox_is_empty(
            supervisor_dir
        ):
            assert time.monotonic() - started < RUN_TIMEOUT_SECONDS, "never drained"
            if not tenant.tick(host):
                time.sleep(0.01)
        drain_seconds = time.monotonic() - started
        program_store = host.program_store
        assert program_store is not None
        records = program_store.submissions()
    finally:
        for submitter in submitters:
            if submitter.poll() is None:
                submitter.kill()
        host.stores.close_all()

    reported = {first}
    for number, submitter in enumerate(submitters):
        stdout_file, stderr_file = submitter_output(tmp_path, number)
        assert submitter.returncode == 0, stderr_file.read_text()
        reported |= set(stdout_file.read_text().split())

    record_ids = [record.id for record in records]
    sequence = [record.applied_seq for record in records]
    assert len(record_ids) == len(set(record_ids)), "a record repeats"
    assert len(sequence) == len(set(sequence)), "applied_seq repeats"
    assert set(record_ids) == reported, "records differ from the reported ids"
    assert all(r.outcome is SubmissionOutcome.APPLIED for r in records)
    assert _inbox_is_empty(supervisor_dir)
    assert quarantined(program_dir(supervisor_dir)) == []
    assert failed(program_dir(supervisor_dir)) == []
    assert drain_seconds < DRAIN_BOUND_SECONDS, measured(
        f"drain of {len(reported)} submissions", drain_seconds, DRAIN_BOUND_SECONDS
    )
    print(
        f"\n{SUBMITTERS} submitters x {BODIES_PER_SUBMITTER} bodies: "
        f"drain in {drain_seconds:.3f}s"
    )


PROJECT_COUNT = 30
TICKS = 5
TICK_DEADLINE_SECONDS = 2.0

#: Asserted bound on the slowest tick, from the module docstring's measurement.
TICK_BOUND_SECONDS = 0.05


class _TickHost:
    stop_requested = False

    def __init__(self, stores: dict[str, Store], program_store: ProgramStore) -> None:
        self._stores = stores
        self.project_ids = tuple(stores)
        self.program_store: ProgramStore | None = program_store

    def store_for(self, project_id: str) -> Store:
        return self._stores[project_id]


def test_the_ticks_program_read_stays_in_bounds_and_opens_no_member_store(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    supervisor_dir = tmp_path / "supervisor"
    (supervisor_dir / LAUNCH_LOGS_DIRNAME).mkdir(parents=True)
    stores: dict[str, Store] = {}
    project_ids = [f"p{index}" for index in range(PROJECT_COUNT)]
    for project_id in project_ids:
        stores[project_id] = Store.open(tmp_path / f"{project_id}.sqlite3")
        stores[project_id].create_node(
            project_id=project_id, kind=NodeKind.SLICE, title="n"
        )
    program_store = ProgramStore.open(program_store_path(supervisor_dir))
    register_program(
        program_store,
        program_payload(
            concept_member=project_ids[0],
            members=[member(project_id) for project_id in project_ids],
        ),
    )

    member_opens: list[Path] = []
    real_open_read_only = Store.open_read_only.__func__  # type: ignore[attr-defined]

    def counting(cls: type[Store], path: Path | None = None, **kwargs: float) -> Store:
        member_opens.append(path if path is not None else Path("?"))
        return real_open_read_only(cls, path, **kwargs)

    monkeypatch.setattr(Store, "open_read_only", classmethod(counting))
    tenant = RunnerTenant(
        settings=ProcessSettings(tick_deadline_seconds=TICK_DEADLINE_SECONDS),
        supervisor_dir=supervisor_dir,
        planners=(),
        popen=lambda *args, **kwargs: None,  # type: ignore[arg-type,return-value]
        cf_run=FakeCf(),
        poll=lambda run_id: None,  # type: ignore[arg-type,return-value]
        now=lambda: datetime.now(UTC),
        monotonic=time.monotonic,
        version_label="sq-test-label",
        project_config=ProjectConfig(
            {project: ProjectSettings(pipeline="p456") for project in project_ids}
        ),
        amoeba_version=TEST_AMOEBA_VERSION,
    )
    host = _TickHost(stores, program_store)
    durations: list[float] = []
    try:
        for _ in range(TICKS):
            started = time.monotonic()
            tenant.tick(host)
            durations.append(time.monotonic() - started)
    finally:
        program_store.close()
        for store in stores.values():
            store.close()

    print(f"\n{PROJECT_COUNT} projects: slowest tick {max(durations):.3f}s")
    assert member_opens == [], "the program read opened a member store"
    assert max(durations) < TICK_BOUND_SECONDS, measured(
        "slowest tick", max(durations), TICK_BOUND_SECONDS
    )
