"""InboxTenant: the apply loop, the quarantine ladder, and the attempt counter.

Driven in-process through ``LocalHost`` — real stores, real files, the real
tick — so every branch is reachable without a subprocess. The full-process
behavior (restarts, a running ``amoeba start``) is covered separately against
the real host.
"""

from __future__ import annotations

from pathlib import Path

from local_host_harness import LocalHost

from amoeba.inbox import pending, submit
from amoeba.process.inbox_tenant import InboxTenant
from amoeba.process.settings import ProcessSettings
from amoeba.store import SubmissionKind, SubmissionOutcome
from amoeba.store.inbox_models import INTENT_BODY

PROJECT = "demo"


def _submit_intent(supervisor_dir: Path, submission_id: str | None = None) -> str:
    return submit(
        project_id=PROJECT,
        kind=SubmissionKind.INTENT,
        payload={INTENT_BODY: {"want": "x"}},
        submitted_by="tester",
        submission_id=submission_id,
        store_dir=supervisor_dir,
    )


# --------------------------------------------------------------------------
# Smoke: the three claims of the apply loop
# --------------------------------------------------------------------------


def test_an_intent_applies_and_its_file_is_deleted(
    supervisor_dir: Path, local_host: LocalHost
) -> None:
    store = local_host.open_project(PROJECT)
    submission_id = _submit_intent(supervisor_dir)

    assert InboxTenant(supervisor_dir).tick(local_host) is True

    record = store.submission(submission_id)
    assert record is not None and record.outcome is SubmissionOutcome.APPLIED
    assert [message.submission_id for message in store.pending_intents(PROJECT)] == [
        submission_id
    ]
    assert pending(supervisor_dir) == []


def test_a_tick_handles_at_most_the_batch_size(
    supervisor_dir: Path, local_host: LocalHost
) -> None:
    local_host.open_project(PROJECT)
    local_host.settings = ProcessSettings(inbox_batch_size=2)
    for _ in range(5):
        _submit_intent(supervisor_dir)

    InboxTenant(supervisor_dir).tick(local_host)

    assert len(pending(supervisor_dir)) == 3


def test_a_tick_stops_early_when_stop_is_requested(
    supervisor_dir: Path, local_host: LocalHost
) -> None:
    local_host.open_project(PROJECT)
    _submit_intent(supervisor_dir)
    local_host.stop_requested = True

    assert InboxTenant(supervisor_dir).tick(local_host) is False
    assert len(pending(supervisor_dir)) == 1


def test_an_empty_inbox_reports_no_work(
    supervisor_dir: Path, local_host: LocalHost
) -> None:
    assert InboxTenant(supervisor_dir).tick(local_host) is False
