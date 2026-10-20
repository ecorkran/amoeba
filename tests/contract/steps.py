"""Per-step driver helpers for the lifecycle proof (slice 110, D4).

``ScenarioDriver`` performs the scenario's steps through the harness, then makes
the assertions the end-state oracle cannot: ordering, atomicity, ownership. Every
failure names its step number.
"""

from __future__ import annotations

from pathlib import Path

from amoeba.store import (
    BlockedKind,
    Channel,
    DetectionOutcome,
    JournalEntry,
    JournalOutcome,
    JournalResolver,
    Node,
    NodeKind,
    NodeStatus,
    Store,
    SubmissionKind,
    SubmissionOutcome,
    project_store_path,
)
from amoeba.upstream.squadron import parse_review_artifact, review_record_id
from contract.harness import HarnessFailure, ProofHarness
from contract.scenario import ALPHA, STEPS, Step
from contract.subscriber import Subscriber

#: Payload keys of a ``resolution`` submission, as the inbox contract documents.
PAYLOAD_BLOCKED_STATE_ID = "blocked_state_id"
PAYLOAD_DETAIL = "detail"

STEP_BY_NUMBER = {step.number: step for step in STEPS}


def expect(step: int, condition: bool, message: str) -> None:
    """Fail naming the step; the oracle cannot say which step broke."""
    if not condition:
        raise HarnessFailure(f"step {step}: {message}")


def only_node(store: Store, project_id: str, kind: NodeKind) -> Node:
    [node] = [n for n in store.nodes_for_project(project_id) if n.kind is kind]
    return node


class ScenarioDriver:
    """Drives the scenario's steps in order, tracking each feed's position."""

    def __init__(self, harness: ProofHarness) -> None:
        self.harness = harness
        self.subscribers: dict[str, Subscriber] = {}

    # -- step 1 ------------------------------------------------------------

    def create_and_watch_projects(self, step: Step) -> None:
        """Start the process, create and watch each project, follow each feed."""
        h = self.harness
        h.start(step.number)
        submissions = [
            (project, submit(project))
            for project in step.projects
            for submit in (h.create_project, h.watch_reviews)
        ]
        for project, submission_id in submissions:
            self._wait_applied(step.number, project, submission_id)
        for project in step.projects:
            self.subscribers[project] = h.follow_project(step.number, project)
            self._wait_baselined(step.number, project)

    def _wait_applied(self, step: int, project: str, submission_id: str) -> None:
        h = self.harness
        path = project_store_path(h.supervisor_dir, project)

        def applied() -> bool:
            if not path.exists():
                return False
            with h.read(project) as store:
                record = store.submission(submission_id)
            return record is not None and record.outcome is SubmissionOutcome.APPLIED

        h.wait_until(step, f"{project} submission {submission_id} to apply", applied)

    def _wait_baselined(self, step: int, project: str) -> None:
        """A review written before the watch is baselined would be ignored."""
        h = self.harness

        def baselined() -> bool:
            with h.read(project) as store:
                watches = store.watches(project)
            return bool(watches) and all(w.baselined_at for w in watches)

        h.wait_until(step, f"{project}'s review watch to be baselined", baselined)

    # -- Runner steps (2, 3, 4, 5, 9, 11) ---------------------------------------

    def run_intent_step(self, step: Step) -> None:
        """Submit the step's intents; on a crash point, die, restart, recover."""
        assert step.proof_step is not None
        h = self.harness
        since = self._positions()
        for project in step.projects:
            h.intent(project, step.proof_step, step.crash_at)
        if step.crash_at is not None:
            h.wait_for_sigkill(step.number)
            h.start(step.number)
        self.wait_expected(step, since)

    def wait_expected(self, step: Step, since: dict[str, int]) -> None:
        for project, kinds in step.expected.items():
            self.harness.wait_for_changes(
                step.number, project, kinds, since=since[project]
            )

    def _positions(self) -> dict[str, int]:
        return {p: len(s.changes) for p, s in self.subscribers.items()}

    # -- assertions for steps 3-5 ---------------------------------------------------

    def check_reported_review(self, step: int) -> None:
        """Step 3: verdict, ledger row, and entry resolution share one commit."""
        with self.harness.read(ALPHA) as store:
            # Read the moment the verdict is visible: it never precedes the
            # resolution, because they commit together.
            [entry] = store.journal_entries(ALPHA)
            [verdict] = store.verdicts(ALPHA)
            [row] = store.detections(ALPHA)
            owned = store.recorded_result_run_ids(ALPHA)
        expect(step, entry.is_resolved, "the verdict is visible but the entry is open")
        expect(
            step,
            (entry.outcome, entry.resolved_by)
            == (JournalOutcome.COMPLETED, JournalResolver.ISSUER),
            f"entry resolved {entry.outcome}/{entry.resolved_by}, not completed/issuer",
        )
        expect(step, row.outcome is DetectionOutcome.RUNNER_ISSUED, "no runner row")
        expect(
            step,
            (row.verdict_id, row.node_id) == (verdict.id, verdict.node_id),
            "the ledger row does not point at the verdict",
        )
        expect(step, self._owns(owned, entry), "the run id is not recorded as owned")

    def check_adopted_review(self, step: int) -> None:
        """Step 4: one verdict for the round, ingested under the Runner's id."""
        with self.harness.read(ALPHA) as store:
            entries = store.journal_entries(ALPHA)
            verdicts = store.verdicts(ALPHA)
            ingested = store.detections(ALPHA, outcome=DetectionOutcome.INGESTED)
            owned = store.recorded_result_run_ids(ALPHA)
        [adopted] = [e for e in entries if e.outcome is JournalOutcome.ADOPTED]
        expect(step, adopted.resolved_by is JournalResolver.RECOVERY, "not recovery")
        expect(step, len(verdicts) == 2, f"{len(verdicts)} verdicts, expected 2")
        [row] = ingested
        parsed = parse_review_artifact(Path(row.path).read_text(encoding="utf-8"))
        expect(
            step,
            row.record_id == review_record_id(parsed),
            "detection's record id differs from the parsed artifact's",
        )
        expect(step, self._owns(owned, adopted), "the adopted run is not owned")

    def check_escalation(self, step: int) -> Node:
        """Step 5: no run found, so one ``unknown`` entry and one escalation.

        Returns the blocked node: the one the lost command was journaled on.
        """
        with self.harness.read(ALPHA) as store:
            unknown = [
                e
                for e in store.journal_entries(ALPHA)
                if e.outcome is JournalOutcome.UNKNOWN
            ]
            escalations = store.messages(ALPHA, channel=Channel.ESCALATION)
            reviewed = only_node(store, ALPHA, NodeKind.SLICE)
        expect(step, len(unknown) == 1, f"{len(unknown)} unknown entries, expected 1")
        expect(step, len(escalations) == 1, f"{len(escalations)} escalations")
        expect(
            step,
            reviewed.status is NodeStatus.BLOCKED_ON_HUMAN,
            "the reviewed slice is not blocked on a human",
        )
        return reviewed

    @staticmethod
    def _owns(owned: dict[str, str], entry: JournalEntry) -> bool:
        """Whether the entry's own run id is recorded as owned by that entry."""
        run_id = entry.result["run_id"] if entry.result else None
        return isinstance(run_id, str) and owned.get(run_id) == entry.id

    # -- step 6 -----------------------------------------------------------------------

    def resolve_blocked_node(self, step: Step, node: Node) -> None:
        """The PM's reply flips the node runnable."""
        h = self.harness
        since = self._positions()
        with h.read(ALPHA) as store:
            blocked = store.blocked_state_for(node.id)
        expect(step.number, blocked is not None, "the node has no open block")
        assert blocked is not None
        expect(step.number, blocked.kind is BlockedKind.HUMAN, "not a human block")
        h.submit(
            ALPHA,
            SubmissionKind.RESOLUTION,
            {PAYLOAD_BLOCKED_STATE_ID: blocked.id, PAYLOAD_DETAIL: "go on"},
        )
        self.wait_expected(step, since)
        with h.read(ALPHA) as store:
            moved = store.get_node(node.id)
        expect(
            step.number,
            moved is not None and moved.status is NodeStatus.RUNNABLE,
            "the node did not become runnable",
        )
