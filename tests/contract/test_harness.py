"""The contract harness works before the scenario depends on it."""

from __future__ import annotations

from pathlib import Path

import pytest

from amoeba.store import ChangeKind, JournalOutcome
from contract.harness import HarnessFailure, ProofHarness
from contract.runner_tenant import CrashPoint, ProofStep
from contract.scenario import ALPHA
from contract.subscriber import Subscriber

START_STEP = 1


def test_start_submit_build_a_tree_and_stop_cleanly(
    proof_harness: ProofHarness,
) -> None:
    proof_harness.start(START_STEP)
    proof_harness.create_project(ALPHA)
    proof_harness.follow_project(START_STEP, ALPHA)

    proof_harness.intent(ALPHA, ProofStep.BUILD_TREE)
    proof_harness.wait_for_changes(START_STEP, ALPHA, [ChangeKind.NODE_CREATED] * 3)
    proof_harness.stop(START_STEP)

    assert proof_harness.process.returncode == 0


def test_a_crash_after_the_journal_is_recovered_on_restart(
    proof_harness: ProofHarness,
) -> None:
    proof_harness.start(START_STEP)
    proof_harness.create_project(ALPHA)
    proof_harness.watch_reviews(ALPHA)
    proof_harness.follow_project(START_STEP, ALPHA)
    proof_harness.intent(ALPHA, ProofStep.BUILD_TREE)
    proof_harness.wait_for_changes(START_STEP, ALPHA, [ChangeKind.NODE_CREATED] * 3)

    proof_harness.intent(ALPHA, ProofStep.LAUNCH_REVIEW, CrashPoint.AFTER_JOURNAL)
    proof_harness.wait_for_sigkill(START_STEP)
    proof_harness.start(START_STEP)

    def entry_is_resolved() -> bool:
        with proof_harness.read(ALPHA) as store:
            entries = store.journal_entries(ALPHA)
        return len(entries) == 1 and entries[0].is_resolved

    proof_harness.wait_until(
        START_STEP, "recovery to resolve the entry", entry_is_resolved
    )
    with proof_harness.read(ALPHA) as store:
        [entry] = store.journal_entries(ALPHA)
    # No run file was written, so recovery finds no match and escalates.
    assert entry.outcome is JournalOutcome.UNKNOWN


def test_a_bootstrap_that_never_becomes_ready_fails_with_its_stderr(
    tmp_path: Path,
) -> None:
    harness = ProofHarness(tmp_path, (ALPHA,), review_fixture=tmp_path / "missing.md")
    try:
        with pytest.raises(HarnessFailure) as failure:
            harness.start(7)
    finally:
        harness.close()

    message = str(failure.value)
    assert "step 7" in message
    assert "bootstrap-1 stderr" in message
    assert "FileNotFoundError" in message


def test_a_wait_that_times_out_names_the_step(proof_harness: ProofHarness) -> None:
    proof_harness.start(START_STEP)

    with pytest.raises(HarnessFailure, match="step 9: timed out"):
        proof_harness.wait_until(
            9, "something that never happens", lambda: False, timeout=0.2
        )


def test_a_subscriber_failure_is_re_raised_at_the_next_wait(
    proof_harness: ProofHarness,
) -> None:
    # No such project: `follow()` raises inside the subscriber's thread.
    proof_harness.add_subscriber(Subscriber(proof_harness.supervisor_dir, "ghost"))

    with pytest.raises(RuntimeError, match="ghost"):
        proof_harness.wait_until(3, "anything", lambda: False, timeout=10.0)


def test_every_path_handed_to_a_subprocess_is_under_tmp_path(
    proof_harness: ProofHarness, tmp_path: Path
) -> None:
    environment = proof_harness.environment()

    for key in ("HOME", "AMOEBA_STORE_DIR"):
        assert Path(environment[key]).resolve().is_relative_to(tmp_path.resolve())
