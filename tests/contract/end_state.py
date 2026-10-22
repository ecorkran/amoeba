"""What each project's store must hold when the scenario ends (slice 110, D5).

Derived from the D4 table's "Proves" column, step by step. A fact repeated is a
count: alpha records six intents because six of its steps are Runner intents.
"""

from __future__ import annotations

from amoeba.store import (
    BlockedKind,
    Channel,
    CommandKind,
    DetectionOutcome,
    JournalOutcome,
    JournalResolver,
    NodeKind,
    NodeStatus,
    SubmissionKind,
    SubmissionOutcome,
    VerdictStanding,
)
from contract.oracle import (
    Category,
    ProjectState,
    blocked_fact,
    counted,
    detection_fact,
    journal_fact,
    message_fact,
    node_fact,
    submission_fact,
    verdict_fact,
)
from contract.scenario import ALPHA, BETA

_APPLIED = SubmissionOutcome.APPLIED

# Alpha's Runner intents: steps 2, 3, 4, 5, 9, 11. Beta's: steps 2 and 9.
_ALPHA_INTENTS = 6
_BETA_INTENTS = 2
# Step 8's two judge samples share one invocation.
_JUDGE_SAMPLES = 2


def declared_state(project_id: str) -> ProjectState:
    """The state ``project_id`` must end in."""
    if project_id == ALPHA:
        return _alpha()
    if project_id == BETA:
        return _beta()
    raise ValueError(f"the scenario declares no end state for {project_id!r}")


def _alpha() -> ProjectState:
    return {
        Category.NODES: counted(
            node_fact(NodeKind.INITIATIVE, NodeStatus.RUNNABLE),
            node_fact(NodeKind.SLICE, NodeStatus.DONE),
            node_fact(NodeKind.GATE, NodeStatus.DONE),
        ),
        # Step 5's escalation, on the reviewed slice (resolved in step 6), and
        # step 9's checkpoint, on the gate (resolved in step 10).
        Category.BLOCKED: counted(
            blocked_fact(NodeKind.SLICE, BlockedKind.HUMAN, True),
            blocked_fact(NodeKind.GATE, BlockedKind.SQ_CHECKPOINT, True),
        ),
        Category.JOURNAL: counted(
            # Steps 3 and 9: the issuer reported its own result.
            *[
                journal_fact(
                    CommandKind.SQ_RUN, JournalOutcome.COMPLETED, JournalResolver.ISSUER
                )
            ]
            * 2,
            # Step 4: recovery found the run and adopted it.
            journal_fact(
                CommandKind.SQ_RUN, JournalOutcome.ADOPTED, JournalResolver.RECOVERY
            ),
            # Step 5: the run's state was unreadable, so recovery escalated.
            journal_fact(
                CommandKind.SQ_RUN, JournalOutcome.UNKNOWN, JournalResolver.RECOVERY
            ),
        ),
        Category.VERDICTS: counted(
            # Steps 3, 4 and 7: a stated review each; step 8's two samples.
            *[verdict_fact(VerdictStanding.STATED, False)] * 3,
            *[verdict_fact(VerdictStanding.STATED, True)] * _JUDGE_SAMPLES,
        ),
        Category.DETECTIONS: counted(
            # Step 3: the Runner's own review. Steps 4 and 7: detection's.
            detection_fact(DetectionOutcome.RUNNER_ISSUED, True),
            *[detection_fact(DetectionOutcome.INGESTED, True)] * 2,
        ),
        Category.MESSAGES: counted(
            *[message_fact(Channel.INTENT, True)] * _ALPHA_INTENTS,
            message_fact(Channel.ESCALATION, False),
        ),
        Category.SUBMISSIONS: counted(
            submission_fact(SubmissionKind.CREATE_PROJECT, _APPLIED),
            submission_fact(SubmissionKind.WATCH_REVIEWS, _APPLIED),
            *[submission_fact(SubmissionKind.INTENT, _APPLIED)] * _ALPHA_INTENTS,
            *[submission_fact(SubmissionKind.RESOLUTION, _APPLIED)] * 2,
            *[submission_fact(SubmissionKind.VERDICT, _APPLIED)] * _JUDGE_SAMPLES,
        ),
    }


def _beta() -> ProjectState:
    return {
        Category.NODES: counted(
            node_fact(NodeKind.INITIATIVE, NodeStatus.RUNNABLE),
            node_fact(NodeKind.SLICE, NodeStatus.RUNNABLE),
            node_fact(NodeKind.GATE, NodeStatus.BLOCKED_ON_SQ_CHECKPOINT),
        ),
        # Step 12's held case: beta's checkpoint is still open.
        Category.BLOCKED: counted(
            blocked_fact(NodeKind.GATE, BlockedKind.SQ_CHECKPOINT, False),
        ),
        Category.JOURNAL: counted(
            journal_fact(
                CommandKind.SQ_RUN, JournalOutcome.COMPLETED, JournalResolver.ISSUER
            ),
        ),
        Category.VERDICTS: counted(),
        Category.DETECTIONS: counted(),
        Category.MESSAGES: counted(
            *[message_fact(Channel.INTENT, True)] * _BETA_INTENTS
        ),
        Category.SUBMISSIONS: counted(
            submission_fact(SubmissionKind.CREATE_PROJECT, _APPLIED),
            submission_fact(SubmissionKind.WATCH_REVIEWS, _APPLIED),
            *[submission_fact(SubmissionKind.INTENT, _APPLIED)] * _BETA_INTENTS,
        ),
    }
