"""D6: detection must not take a file the Runner recorded as external.

A run's review sits in a directory detection watches. While the run's entry is
unresolved detection defers; once ingestion has recorded the file as
``runner_issued``, detection's ledger holds the file's key and skips it. That holds
for a completed run and for a paused run, whose last review is the review behind its
checkpoint.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from detection_harness import PROJECT, SLICE_NAME, DetectionRig
from local_host_harness import LocalHost
from routing_helpers import PROJECT as ROUTING_PROJECT
from sq_stub_scripts import REVIEWS_DIR, RunScript, single_review

from amoeba.process import ProcessSettings, RunOutcome, RunOutcomeDocument
from amoeba.runner.finish import record
from amoeba.runner.launch import PARAM_PARAMS, PARAM_PIPELINE
from amoeba.runner.observed import RunEnded
from amoeba.store import (
    PARAM_CHECKOUT,
    PARAM_RUN_ID,
    ChangeKind,
    CommandKind,
    DetectionOutcome,
    JournalEntry,
    JournalOutcome,
    NodeKind,
)

RUN_ID = "amoeba-20261024T101500Z-0123456789ab"
AUTO_RESUME_LIMIT = ProcessSettings().auto_resume_limit
VERSION_LABEL = "sq-test-label"
SETTLE_SCANS = 2


@pytest.fixture
def host(tmp_path: Path) -> Iterator[LocalHost]:
    supervisor_dir = tmp_path / "supervisor"
    supervisor_dir.mkdir()
    local = LocalHost(supervisor_dir, ProcessSettings())
    try:
        yield local
    finally:
        local.stores.close_all()


def test_the_projects_agree_on_their_name() -> None:
    """The routing helpers and the detection harness share one project id."""
    assert ROUTING_PROJECT == PROJECT


def _open_run(
    host: LocalHost, tmp_path: Path
) -> tuple[DetectionRig, Path, JournalEntry, RunScript]:
    """A baselined watch, a run journaled on a step, and its review on disk."""
    checkout = tmp_path / "checkout"
    reviews_dir = checkout / REVIEWS_DIR
    reviews_dir.mkdir(parents=True)
    rig = DetectionRig(host, reviews_dir)
    slice_id = rig.seed_slice_node()
    rig.watch()
    rig.run_scans()  # baselines the empty directory
    step = rig.store.create_node(
        project_id=PROJECT,
        kind=NodeKind.PHASE_OR_ARTIFACT,
        title="tasks",
        parent_id=slice_id,
    )
    entry = rig.store.journal_issue(
        step.id,
        kind=CommandKind.SQ_RUN,
        parameters={
            PARAM_PIPELINE: "p5",
            PARAM_PARAMS: {},
            PARAM_RUN_ID: RUN_ID,
            PARAM_CHECKOUT: str(checkout),
        },
    )
    script = single_review(SLICE_NAME)
    _write(checkout, script)
    return rig, checkout, entry, script


def _ledger_outcomes(rig: DetectionRig) -> list[DetectionOutcome]:
    return [
        d.outcome
        for d in rig.store.detections(PROJECT)
        if d.outcome is not DetectionOutcome.BASELINE
    ]


@pytest.mark.parametrize("outcome", [RunOutcome.COMPLETED, RunOutcome.PAUSED])
def test_detection_skips_the_review_the_runner_recorded(
    host: LocalHost, tmp_path: Path, outcome: RunOutcome
) -> None:
    rig, _, entry, script = _open_run(host, tmp_path)

    rig.run_scans(SETTLE_SCANS + 1)
    assert rig.store.verdicts(PROJECT) == [], "detection defers while the entry is open"

    _ingest(rig, entry, script, outcome)
    rig.run_scans(SETTLE_SCANS + 2)

    assert _ledger_outcomes(rig) == [DetectionOutcome.RUNNER_ISSUED]
    assert len(rig.store.verdicts(PROJECT)) == 1, "the Runner's verdict, no second one"
    kinds = {c.kind for c in rig.store.changes(PROJECT, limit=100)}
    assert ChangeKind.REVIEW_DETECTED not in kinds


def test_control_detection_ingests_the_file_when_the_runner_did_not_record_it(
    host: LocalHost, tmp_path: Path
) -> None:
    """Without the Runner's ledger row the same file is taken as external."""
    rig, _, entry, _ = _open_run(host, tmp_path)
    rig.store.journal_resolve(entry.id, outcome=JournalOutcome.COMPLETED, result={})

    rig.run_scans(SETTLE_SCANS + 2)

    assert _ledger_outcomes(rig) == [DetectionOutcome.INGESTED]


def _write(checkout: Path, script: RunScript) -> None:
    for relative, text in script.files.items():
        target = checkout / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")


def _ingest(
    rig: DetectionRig, entry: JournalEntry, script: RunScript, outcome: RunOutcome
) -> None:
    extra: dict[str, object] = {}
    if outcome is RunOutcome.PAUSED:
        extra["checkpoint"] = {"kind": "awaits_human", "step": "tasks-0"}
    document = RunOutcomeDocument.model_validate(
        {
            "run_id": RUN_ID,
            "outcome": outcome.value,
            "status": outcome.value,
            **script.document,
            **extra,
        }
    )
    record(
        rig.store,
        entry,
        RunEnded(document),
        VERSION_LABEL,
        AUTO_RESUME_LIMIT,
    )
