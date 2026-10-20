"""The lifecycle proof: the scenario's twelve steps against real processes.

Slice 110, D4. Steps 7-12 and the oracles extend this test in later tasks.
"""

from __future__ import annotations

from contract.harness import ProofHarness
from contract.steps import STEP_BY_NUMBER, ScenarioDriver


def test_the_lifecycle_proof(proof_harness: ProofHarness) -> None:
    driver = ScenarioDriver(proof_harness)

    driver.create_and_watch_projects(STEP_BY_NUMBER[1])
    driver.run_intent_step(STEP_BY_NUMBER[2])

    driver.run_intent_step(STEP_BY_NUMBER[3])
    driver.check_reported_review(3)

    driver.run_intent_step(STEP_BY_NUMBER[4])
    driver.check_adopted_review(4)

    driver.run_intent_step(STEP_BY_NUMBER[5])
    blocked = driver.check_escalation(5)

    driver.resolve_blocked_node(STEP_BY_NUMBER[6], blocked)
