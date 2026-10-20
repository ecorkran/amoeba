"""The proof's scenario, as data (slice 110, D4).

Twelve steps, in the order a consumer follows them, across two projects. This
module holds no driver logic and does no I/O: it states, for each step, who acts,
what they do, and which changes must reach the project's feed afterwards.

``expected`` is a containment set, not an exact list: a step waits until its
projects' feeds hold *at least* these kinds after the step began. Exactness is
the end-state oracle's and the feed-replay oracle's job, once, at the end.

`beta` takes part in only steps 1, 2, and 9. It cannot be dropped: the keying
checks need a second project, and step 12's held case needs an owned paused run
whose gate is still open.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import timedelta
from enum import StrEnum

from amoeba.store import ChangeKind
from contract.runner_tenant import CrashPoint, ProofStep

#: The two projects the scenario runs across.
ALPHA = "alpha"
BETA = "beta"

#: How far before its step's wall-clock time every paused run file the stand-in
#: writes is dated. Far past any retention pruning could plausibly use, so the
#: proof asserts which runs are selected and kept, never the retention itself.
STANDIN_RUN_AGE = timedelta(days=365)


class Actor(StrEnum):
    """Who performs a step."""

    PM = "pm"
    RUNNER = "runner"
    JUDGE = "judge"
    EXTERNAL = "external"
    PROCESS = "process"


class Action(StrEnum):
    """What a step does, in the driver's vocabulary."""

    CREATE_AND_WATCH_PROJECTS = "create_and_watch_projects"
    RUNNER_INTENT = "runner_intent"
    RESOLVE_BLOCKED_NODE = "resolve_blocked_node"
    WRITE_EXTERNAL_REVIEW = "write_external_review"
    SUBMIT_JUDGE_SAMPLES = "submit_judge_samples"
    STOP_SUBMIT_AND_START = "stop_submit_and_start"
    PRUNE_PAUSED_RUNS = "prune_paused_runs"


@dataclass(frozen=True)
class Step:
    """One row of the D4 table.

    ``crash_at`` set means the resident process kills itself inside the step and
    the driver restarts it. ``expected`` maps a project id to the change kinds
    its feed must hold afterwards.
    """

    number: int
    actor: Actor
    action: Action
    projects: tuple[str, ...]
    proof_step: ProofStep | None = None
    crash_at: CrashPoint | None = None
    expected: Mapping[str, tuple[ChangeKind, ...]] = field(
        default_factory=dict[str, tuple[ChangeKind, ...]]
    )


# Every Runner step is an intent, and an intent posts a message on the feed.
_INTENT = (ChangeKind.MESSAGE_POSTED,)
_THREE_NODES = (ChangeKind.NODE_CREATED,) * 3
# A Runner-reported review writes a verdict and a silent `runner_issued` ledger
# row; detection's `ingested` row is the one that announces itself.
_REPORTED = (ChangeKind.VERDICT_RECORDED,)
_DETECTED = (ChangeKind.VERDICT_RECORDED, ChangeKind.REVIEW_DETECTED)
_NODE_MOVED = (ChangeKind.NODE_STATUS_CHANGED,)

STEPS: tuple[Step, ...] = (
    Step(1, Actor.PM, Action.CREATE_AND_WATCH_PROJECTS, (ALPHA, BETA)),
    Step(
        2,
        Actor.RUNNER,
        Action.RUNNER_INTENT,
        (ALPHA, BETA),
        proof_step=ProofStep.BUILD_TREE,
        expected={ALPHA: _INTENT + _THREE_NODES, BETA: _INTENT + _THREE_NODES},
    ),
    Step(
        3,
        Actor.RUNNER,
        Action.RUNNER_INTENT,
        (ALPHA,),
        proof_step=ProofStep.LAUNCH_REVIEW,
        expected={ALPHA: _INTENT + _REPORTED},
    ),
    Step(
        4,
        Actor.RUNNER,
        Action.RUNNER_INTENT,
        (ALPHA,),
        proof_step=ProofStep.LAUNCH_REVIEW,
        crash_at=CrashPoint.AFTER_SIDE_EFFECT,
        expected={ALPHA: _INTENT + _DETECTED},
    ),
    Step(
        5,
        Actor.RUNNER,
        Action.RUNNER_INTENT,
        (ALPHA,),
        proof_step=ProofStep.LAUNCH_REVIEW,
        crash_at=CrashPoint.AFTER_JOURNAL,
        expected={ALPHA: _INTENT + _INTENT + _NODE_MOVED},
    ),
    Step(
        6,
        Actor.PM,
        Action.RESOLVE_BLOCKED_NODE,
        (ALPHA,),
        expected={ALPHA: _NODE_MOVED},
    ),
    Step(
        7,
        Actor.EXTERNAL,
        Action.WRITE_EXTERNAL_REVIEW,
        (ALPHA,),
        expected={ALPHA: _DETECTED},
    ),
    Step(
        8,
        Actor.JUDGE,
        Action.SUBMIT_JUDGE_SAMPLES,
        (ALPHA,),
        expected={ALPHA: (ChangeKind.VERDICT_RECORDED,) * 2},
    ),
    Step(
        9,
        Actor.RUNNER,
        Action.RUNNER_INTENT,
        (ALPHA, BETA),
        proof_step=ProofStep.CHECKPOINT,
        expected={ALPHA: _INTENT + _NODE_MOVED, BETA: _INTENT + _NODE_MOVED},
    ),
    Step(
        10,
        Actor.PROCESS,
        Action.STOP_SUBMIT_AND_START,
        (ALPHA,),
        expected={ALPHA: _NODE_MOVED},
    ),
    Step(
        11,
        Actor.RUNNER,
        Action.RUNNER_INTENT,
        (ALPHA,),
        proof_step=ProofStep.FINISH,
        expected={ALPHA: _INTENT + _NODE_MOVED * 2},
    ),
    # The command reads every project's store; `beta` is not an actor here.
    Step(12, Actor.PM, Action.PRUNE_PAUSED_RUNS, (ALPHA,)),
)
