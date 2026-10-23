"""The stand-in for Squadron's side effects (slice 110, D3).

The proof is about Amoeba's contract, not Squadron: a real ``sq review`` needs a
model provider, costs money, and is not deterministic. What recovery and
pruning read is the outcome document ``sq runs wait`` prints, and what detection
reads is a review file, so those are what is written here (the outcome through
the stub ``sq``, the review derived from a captured fixture so its format stays
the real one). ``write_run_file`` writes Squadron's own run-state file, which
nothing in Amoeba reads since slice 120; the pruning tests use it to prove that.

Shared by the proof Runner (which launches work) and the scenario driver (which
plays the PM launching a review of its own in step 7).
"""

from __future__ import annotations

import json
import re
import uuid
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path

from sq_stub import write_outcome_document

from amoeba.process import RunOutcome

#: The pipeline every stand-in run claims to be.
STANDIN_PIPELINE = "review"

#: Run-file statuses the stand-in writes.
STATUS_COMPLETED = RunOutcome.COMPLETED.value
STATUS_PAUSED = RunOutcome.PAUSED.value

_RUN_ID_FIELD = re.compile(r"^runId:.*$", re.MULTILINE)


def new_run_id(now: datetime) -> str:
    """A run id in Squadron's ``run-{date}-{slug}-{uuid8}`` form."""
    return f"run-{now:%Y%m%d}-{STANDIN_PIPELINE}-{uuid.uuid4().hex[:8]}"


def _timestamp(moment: datetime) -> str:
    """Squadron's run-file timestamp form: UTC, microseconds, a ``Z`` suffix."""
    return (
        moment.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
    )


def write_run_file(
    runs_dir: Path,
    fixture: Path,
    *,
    run_id: str,
    params: Mapping[str, object],
    started_at: datetime,
    updated_at: datetime,
    status: str,
) -> Path:
    """Write ``{run_id}.json`` into ``runs_dir``, shaped like the real fixture.

    Only the fields the observers and pruning read are set; everything else is
    the fixture's own. A finished run drops the fixture's checkpoint, since a
    completed run has none.
    """
    payload = json.loads(fixture.read_text(encoding="utf-8"))
    payload.update(
        run_id=run_id,
        pipeline=STANDIN_PIPELINE,
        params=dict(params),
        started_at=_timestamp(started_at),
        updated_at=_timestamp(updated_at),
        status=status,
    )
    if status == STATUS_COMPLETED:
        payload["checkpoint"] = None
    path = runs_dir / f"{run_id}.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def write_outcome(
    home: Path,
    *,
    run_id: str,
    started_at: datetime,
    updated_at: datetime,
    status: str,
) -> Path:
    """Write the stub ``sq``'s outcome document for a stand-in run.

    This is what ``sq runs wait`` prints for the run: recovery and pruning read
    it through the stub, never the run file. A paused run carries the checkpoint
    time pruning requires.
    """
    paused = status == STATUS_PAUSED
    return write_outcome_document(
        home,
        {
            "run_id": run_id,
            "outcome": status,
            "status": status,
            "pipeline": STANDIN_PIPELINE,
            "started_at": _timestamp(started_at),
            "updated_at": _timestamp(updated_at),
            "checkpoint": {"paused_at": _timestamp(updated_at)} if paused else None,
        },
    )


def render_review(template: str, run_id: str) -> str:
    """A review artifact for one run: the template with that run's id.

    The run id is the field that differs between reviews, so each run gets its
    own parsed-content record id and its own bytes.
    """
    rendered, replaced = _RUN_ID_FIELD.subn(f"runId: {run_id}", template, count=1)
    if replaced != 1:
        raise ValueError("the review template has no runId field to replace")
    return rendered
