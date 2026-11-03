"""The real answering stage over the real ``sq`` and real models (slice 144, Task 14).

The stage, the store and the gate are production code; ``cf config get`` is faked
(the target is ``main``) and git is real. Each case runs once to a settled record:
nothing retries, and a wrong result fails the test.
"""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from answerer_settings import answerer_settings
from live_settings import LiveSettings
from question_harness import seed_question
from runner.answering.launch_rig import LaunchRig, build_launch_rig
from runner.observe_support import Host

from amoeba.process import RunPoll, poll_run
from amoeba.runner.answering.stage import AnsweringStage
from amoeba.runner.budget import TickBudget
from amoeba.runner.faults import NodeContext, TickFaults
from amoeba.runner.observe import RunObserver
from amoeba.store import (
    AnsweredBy,
    Node,
    QuestionRecord,
    QuestionState,
    Store,
)

SETTLE_TIMEOUT_SECONDS = 420.0
POLL_PAUSE_SECONDS = 2.0
POLL_CALL_TIMEOUT_SECONDS = 15.0
_SETTLED = (QuestionState.ANSWERED, QuestionState.DECLINED)


@dataclass(frozen=True)
class LiveStage:
    """A pending question on slice 132, and the stage that answers it."""

    rig: LaunchRig
    stage: AnsweringStage
    store: Store

    def seed_pm_answer(
        self, node: Node, question: str, answer: str, when: datetime
    ) -> QuestionRecord:
        """A question the PM answered, as precedent for the stage."""
        return seed_question(
            self.store,
            node.id,
            state=QuestionState.ANSWERED,
            answered_by=AnsweredBy.PM,
            question=question,
            answer=answer,
            updated_at=when,
        )

    def settle(self) -> QuestionRecord:
        """Run the stage until the question under test is answered or declined."""
        deadline = time.monotonic() + SETTLE_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            budget = TickBudget(time.monotonic() + 60.0, Host(), time.monotonic)
            self.stage.run(budget, TickFaults())
            record = self.store.question(self.rig.record.id)
            assert record is not None
            if record.state in _SETTLED:
                return record
            time.sleep(POLL_PAUSE_SECONDS)
        raise AssertionError(f"question {self.rig.record.id} did not settle in time")


def build_live_stage(
    tmp_path: Path, store: Store, live: LiveSettings, question: str
) -> LiveStage:
    settings = answerer_settings(
        rules_paths=("CLAUDE.md",),
        passages_max_chars=1_000_000,
        answer_model=live.answer_model,
        check_model=live.check_model,
        max_cost_usd=live.max_cost_usd,
    )
    rig = build_launch_rig(
        tmp_path,
        store,
        settings=settings,
        popen_factory=subprocess.Popen,
        question=question,
    )

    def poll(run_id: str) -> RunPoll:
        return poll_run(run_id, timeout_seconds=POLL_CALL_TIMEOUT_SECONDS)

    observer = RunObserver(
        supervisor_dir=rig.supervisor_dir,
        tracker=rig.context.tracker,
        poll=poll,
        now=lambda: datetime.now(UTC),
        monotonic=time.monotonic,
        launch_grace_seconds=120.0,
        run_poll_interval_seconds=POLL_PAUSE_SECONDS,
    )
    stage = AnsweringStage(
        store=store,
        project_id=rig.context.project_id,
        launch=rig.context,
        observer=observer,
        node_context=NodeContext(),
    )
    return LiveStage(rig, stage, store)
