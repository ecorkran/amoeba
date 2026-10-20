"""Steps 7-11 of the lifecycle proof, and the final oracle checks (slice 110, D4/D5).

Steps 1-6 live in ``steps.py``. This module adds external work, the Judge path,
checkpoints, down-time submissions, and finish, then runs both oracles.
"""

from __future__ import annotations

from datetime import UTC, datetime

from amoeba.store import (
    BlockedKind,
    DetectionOutcome,
    NodeKind,
    NodeStatus,
    RecordSource,
    ReviewVerdict,
    SubmissionKind,
    VerdictDerivation,
    VerdictStanding,
)
from contract.end_state import declared_state
from contract.harness import RUN_FIXTURE
from contract.oracle import diff_state, locality_problems, read_state, replay_problems
from contract.scenario import ALPHA, BETA, STANDIN_RUN_AGE, Step
from contract.standin import (
    STATUS_PAUSED,
    new_run_id,
    render_review,
    write_run_file,
)
from contract.steps import (
    PAYLOAD_BLOCKED_STATE_ID,
    PAYLOAD_DETAIL,
    ScenarioDriver,
    expect,
    only_node,
)

#: What the Judge's two samples share (107: one invocation, several samples).
JUDGE_INVOCATION_ID = "proof-judge-invocation"
JUDGE_REVIEW_TYPE = "judge"
JUDGE_ACTOR = "proof-judge"
JUDGE_SAMPLES = 2


def judge_sample_payload(node_id: str) -> dict[str, object]:
    """A ``verdict`` submission payload, as the inbox contract documents it."""
    return {
        "node_id": node_id,
        "verdict": ReviewVerdict.PASS.value,
        "derivation": VerdictDerivation.STATED.value,
        "fallback_used": False,
        "findings_parsed": True,
        "provider_failure": False,
        "review_type": JUDGE_REVIEW_TYPE,
        "model": "proof-judge-model",
        "findings": [],
        "upstream": "squadron",
        "upstream_version": "0.0.0-proof",
        "source": RecordSource.STDOUT_JSON.value,
        "judge_invocation_id": JUDGE_INVOCATION_ID,
    }


class LateStepsDriver(ScenarioDriver):
    """Steps 7-11, then the oracles, on top of steps 1-6."""

    # -- step 7 ---------------------------------------------------------------

    def write_external_review(self, step: Step) -> None:
        """The PM launches a review of their own: a file and an unowned paused run."""
        h = self.harness
        since = self._positions()
        now = datetime.now(UTC)
        run_id = new_run_id(now)
        write_run_file(
            h.runs_dir,
            RUN_FIXTURE,
            run_id=run_id,
            params={},
            started_at=now,
            updated_at=now - STANDIN_RUN_AGE,
            status=STATUS_PAUSED,
        )
        review_path = h.reviews_dirs[ALPHA] / f"{run_id}.md"
        review_path.write_text(
            render_review(h.review_fixture.read_text(encoding="utf-8"), run_id),
            encoding="utf-8",
        )
        self.wait_expected(step, since)

        with h.read(ALPHA) as store:
            earlier, latest = store.detections(ALPHA, outcome=DetectionOutcome.INGESTED)
            assert latest.verdict_id is not None
            verdict = store.verdict(latest.verdict_id)
            changes = store.finding_changes(latest.verdict_id)
        expect(step.number, verdict is not None, "detection recorded no verdict")
        assert verdict is not None
        expect(
            step.number,
            verdict.provenance.source_path == str(review_path),
            "the verdict does not name the file it came from",
        )
        expect(step.number, verdict.journal_entry_id is None, "no entry launched it")
        expect(
            step.number,
            changes.comparable and changes.previous_verdict_id == earlier.verdict_id,
            "the review is not compared with step 4's round",
        )

    # -- step 8 ---------------------------------------------------------------

    def submit_judge_samples(self, step: Step) -> None:
        """Two samples of one invocation, through the inbox path 140 will use."""
        h = self.harness
        since = self._positions()
        with h.read(ALPHA) as store:
            reviewed = only_node(store, ALPHA, NodeKind.SLICE)
        for _ in range(JUDGE_SAMPLES):
            h.submit(
                ALPHA,
                SubmissionKind.VERDICT,
                judge_sample_payload(reviewed.id),
                submitted_by=JUDGE_ACTOR,
            )
        self.wait_expected(step, since)

        with h.read(ALPHA) as store:
            samples = [
                v
                for v in store.verdicts(ALPHA)
                if v.judge_invocation_id == JUDGE_INVOCATION_ID
            ]
        expect(step.number, len(samples) == JUDGE_SAMPLES, "samples not recorded")
        expect(
            step.number,
            all(v.standing is VerdictStanding.STATED for v in samples),
            "a sample is not stated",
        )

    # -- step 9 ---------------------------------------------------------------

    def check_checkpoints(self, step: int) -> None:
        """Each gate holds a checkpoint naming a run its project owns."""
        for project in (ALPHA, BETA):
            with self.harness.read(project) as store:
                gate = only_node(store, project, NodeKind.GATE)
                owned = store.recorded_result_run_ids(project)
            run_id = gate.sq.run_id
            expect(step, run_id is not None, f"{project}'s gate names no run")
            expect(
                step,
                gate.status is NodeStatus.BLOCKED_ON_SQ_CHECKPOINT,
                f"{project}'s gate is {gate.status}",
            )
            expect(step, run_id in owned, f"{project} does not own run {run_id}")

    # -- step 10 --------------------------------------------------------------

    def stop_submit_and_start(self, step: Step) -> None:
        """A submission made while the process is down is applied on start."""
        h = self.harness
        since = self._positions()
        with h.read(ALPHA) as store:
            gate = only_node(store, ALPHA, NodeKind.GATE)
            blocked = store.blocked_state_for(gate.id)
        expect(step.number, blocked is not None, "the gate holds no checkpoint")
        assert blocked is not None
        expect(step.number, blocked.kind is BlockedKind.SQ_CHECKPOINT, "wrong block")

        h.stop(step.number)
        submission_id = h.submit(
            ALPHA,
            SubmissionKind.RESOLUTION,
            {PAYLOAD_BLOCKED_STATE_ID: blocked.id, PAYLOAD_DETAIL: "continue"},
        )
        with h.read(ALPHA) as store:
            applied_while_down = store.submission(submission_id) is not None
        expect(step.number, not applied_while_down, "applied with no process running")

        h.start(step.number)
        self._wait_applied(step.number, ALPHA, submission_id)
        self.wait_expected(step, since)
        with h.read(ALPHA) as store:
            moved = store.get_node(gate.id)
        expect(
            step.number,
            moved is not None and moved.status is NodeStatus.RUNNABLE,
            "the gate did not become runnable",
        )

    # -- step 11 --------------------------------------------------------------

    def check_finished(self, step: int) -> None:
        """Alpha is done; beta's checkpoint is still open."""
        with self.harness.read(ALPHA) as store:
            alpha = {n.kind: n.status for n in store.nodes_for_project(ALPHA)}
        with self.harness.read(BETA) as store:
            beta_gate = only_node(store, BETA, NodeKind.GATE)
        expect(step, alpha[NodeKind.SLICE] is NodeStatus.DONE, "alpha's slice")
        expect(step, alpha[NodeKind.GATE] is NodeStatus.DONE, "alpha's gate")
        expect(
            step,
            beta_gate.status is NodeStatus.BLOCKED_ON_SQ_CHECKPOINT,
            "beta's checkpoint was disturbed",
        )

    # -- the oracles ----------------------------------------------------------

    def check_oracles(self, step: int) -> None:
        """Compare each store with its declared end state and with its feed."""
        h = self.harness
        h.wait_until(step, "every subscriber to catch up", self._caught_up)
        problems: list[str] = []
        changes = {p: list(s.changes) for p, s in self.subscribers.items()}
        ledger_paths: dict[str, list[str]] = {}
        for project in (ALPHA, BETA):
            with h.read(project) as store:
                state = read_state(store, project, h.reviews_dirs[project])
                statuses = {n.id: n.status for n in store.nodes_for_project(project)}
                ledger_paths[project] = [d.path for d in store.detections(project)]
                head = store.change_head(project)
                fresh = store.changes(project, after=0, limit=max(head, 1))
            problems += diff_state(project, declared_state(project), state)
            problems += replay_problems(changes[project], statuses)
            if [c.seq for c in fresh] != [c.seq for c in changes[project]]:
                problems.append(f"{project}: the live feed differs from a fresh read")
        problems += locality_problems(
            h.supervisor_dir, (ALPHA, BETA), h.reviews_dirs, changes, ledger_paths
        )
        expect(step, not problems, "\n" + "\n".join(problems))

    def _caught_up(self) -> bool:
        for project, subscriber in self.subscribers.items():
            with self.harness.read(project) as store:
                head = store.change_head(project)
            if not subscriber.changes or subscriber.changes[-1].seq != head:
                return False
        return True
