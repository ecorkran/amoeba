"""The lifecycle proof: the scenario's steps against real processes.

Slice 110, D4. Step 12 prunes against the end state the oracles just checked.
"""

from __future__ import annotations

from contract.harness import ProofHarness
from contract.steps import STEP_BY_NUMBER
from contract.steps_late import LateStepsDriver
from contract.steps_prune import prune_paused_runs


def test_the_lifecycle_proof(proof_harness: ProofHarness) -> None:
    driver = LateStepsDriver(proof_harness)

    driver.create_and_watch_projects(STEP_BY_NUMBER[1])
    driver.run_intent_step(STEP_BY_NUMBER[2])

    driver.run_intent_step(STEP_BY_NUMBER[3])
    driver.check_reported_review(3)

    driver.run_intent_step(STEP_BY_NUMBER[4])
    driver.check_adopted_review(4)

    driver.run_intent_step(STEP_BY_NUMBER[5])
    blocked = driver.check_escalation(5)

    driver.resolve_blocked_node(STEP_BY_NUMBER[6], blocked)
    driver.write_external_review(STEP_BY_NUMBER[7])
    driver.submit_judge_samples(STEP_BY_NUMBER[8])

    driver.run_intent_step(STEP_BY_NUMBER[9])
    driver.check_checkpoints(9)

    driver.stop_submit_and_start(STEP_BY_NUMBER[10])

    driver.run_intent_step(STEP_BY_NUMBER[11])
    driver.check_finished(11)

    driver.check_oracles(11)

    prune_paused_runs(proof_harness, STEP_BY_NUMBER[12], driver.external_run_id)
