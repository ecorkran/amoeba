"""The continuation act's pre-poll, wait, run-missing and observe branches (D4)."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest

from amoeba.process import (
    PollFailure,
    RunCheckpoint,
    RunOutcome,
    RunOutcomeDocument,
    RunPoll,
)
from amoeba.runner.decide import ResumeRun
from amoeba.runner.dispatch.params import PARAM_DISPATCH_CHECK
from amoeba.runner.faults import FaultKind, TickFaults
from amoeba.runner.finish import RESULT_RESUME_FAILURE
from amoeba.runner.launch import LAUNCH_LOGS_DIRNAME, LaunchTracker, log_paths
from amoeba.runner.resolutions.act import Acted, ContinuationActs
from amoeba.runner.resolutions.vocabulary import (
    PARAM_RESUME_CAUSE,
    PARAM_RESUME_SKIPPED,
    RESUME_SKIPPED_RUN_NOT_AT_PAUSE,
    ResumeCause,
)
from amoeba.store import (
    PARAM_CHECKOUT,
    PARAM_CONTINUATION,
    PARAM_CONTINUES,
    PARAM_RESOLUTION,
    PARAM_RUN_ID,
    CommandKind,
    JournalEntry,
    JournalOutcome,
    NodeStatus,
    Store,
)
from runner.dispatch.cf_world import budget_allowing, generous_budget
from runner.observe_support import Child, ScriptedPoll
from runner.resolutions.resolution_support import (
    PAUSED_AT,
    block_and_resolve,
    design_step,
    finished_run,
    paused_document,
)
from runner.tick_support import PROJECT

CHECKOUT = "/work/a"


class RecordingPopen:
    """A fake ``Popen``: remembers each start and returns a child that never exits."""

    def __init__(self) -> None:
        self.argvs: list[list[str]] = []
        self.kwargs: list[dict[str, Any]] = []
        self.error: OSError | None = None
        self.open_entries: list[int] = []
        self.store: Store | None = None

    def __call__(self, argv: list[str], **kwargs: Any) -> Child:
        if self.store is not None:
            self.open_entries.append(
                len(self.store.unresolved_journal_entries(PROJECT))
            )
        if self.error is not None:
            raise self.error
        self.argvs.append(argv)
        self.kwargs.append(kwargs)
        return Child(None)


class Rig:
    """A paused step, its resume action, and the act under test."""

    def __init__(self, store: Store, tmp_path: Path) -> None:
        self.store = store
        self.node = design_step(store)
        self.entry: JournalEntry = finished_run(
            store,
            self.node,
            RunOutcome.PAUSED,
            document=paused_document("placeholder"),
            checkout=CHECKOUT,
        )
        self.run_id = str(self.entry.parameters[PARAM_RUN_ID])
        self.poll = ScriptedPoll()
        self.supervisor_dir = tmp_path / "supervisor"
        (self.supervisor_dir / LAUNCH_LOGS_DIRNAME).mkdir(parents=True)
        self.tracker = LaunchTracker()
        self.popen = RecordingPopen()
        self.popen.store = store
        self.acts = ContinuationActs(
            store=store,
            supervisor_dir=self.supervisor_dir,
            poll_run=self.poll,
            tracker=self.tracker,
            popen=self.popen,
            version_label="sq-label",
        )
        self.faults = TickFaults()

    def resume(self) -> ResumeRun:
        return ResumeRun(
            self.node.id,
            self.run_id,
            self.entry.id,
            "b-1",
            Path(CHECKOUT),
            cause=ResumeCause.RESOLUTION,
        )

    def answer(self, *polls: RunPoll) -> None:
        self.poll.answers.extend(polls)

    def entries(self) -> list[JournalEntry]:
        return self.store.journal_entries(PROJECT, node_id=self.node.id)

    def paused(self, offset: int = 0) -> RunOutcomeDocument:
        return RunOutcomeDocument(
            run_id=self.run_id,
            outcome=RunOutcome.PAUSED,
            checkpoint=RunCheckpoint(paused_at=PAUSED_AT + timedelta(minutes=offset)),
        )


@pytest.fixture
def rig(store: Store, tmp_path: Path) -> Rig:
    return Rig(store, tmp_path)


def test_a_spent_budget_polls_and_writes_nothing(rig: Rig) -> None:
    result = rig.acts.act(rig.resume(), budget_allowing(0), rig.faults)

    assert result is Acted.CUT_OFF
    assert rig.poll.asked == [] and len(rig.entries()) == 1


def test_a_failed_pre_poll_writes_nothing_and_records_a_fault(rig: Rig) -> None:
    rig.answer(PollFailure("sq timed out"))

    result = rig.acts.act(rig.resume(), generous_budget(), rig.faults)

    assert result is Acted.WAITED
    assert len(rig.entries()) == 1
    [fault] = list(rig.faults)
    assert fault.kind is FaultKind.RUN_OBSERVATION_FAILED
    assert fault.node_id == rig.node.id and "sq timed out" in fault.detail


def test_missing_run_launches_nothing(rig: Rig) -> None:
    rig.answer(RunOutcomeDocument(run_id=rig.run_id, outcome=RunOutcome.NOT_FOUND))

    result = rig.acts.act(rig.resume(), generous_budget(), rig.faults)

    assert result is Acted.WROTE
    continuation = rig.entries()[-1]
    assert continuation.parameters[PARAM_CONTINUATION] == "resume"
    assert continuation.outcome is JournalOutcome.FAILED
    assert continuation.result is not None
    assert continuation.result[RESULT_RESUME_FAILURE] == "run_missing"
    node = rig.store.get_node(rig.node.id)
    assert node is not None and node.status is NodeStatus.BLOCKED_ON_HUMAN


def test_a_run_that_moved_on_is_observed_not_resumed(rig: Rig) -> None:
    rig.answer(rig.paused(offset=30))

    result = rig.acts.act(rig.resume(), generous_budget(), rig.faults)

    assert result is Acted.WROTE
    observation = rig.entries()[-1]
    assert not observation.is_resolved
    assert PARAM_CONTINUATION not in observation.parameters, "not a resume"
    assert observation.parameters[PARAM_RESUME_SKIPPED] == (
        RESUME_SKIPPED_RUN_NOT_AT_PAUSE
    )
    assert rig.popen.argvs == []


def test_the_observation_carries_the_continued_run_and_names_both_ends(
    rig: Rig,
) -> None:
    rig.answer(rig.paused(offset=30))

    rig.acts.act(rig.resume(), generous_budget(), rig.faults)

    observation = rig.entries()[-1]
    assert observation.kind is CommandKind.SQ_RUN
    assert observation.parameters[PARAM_RUN_ID] == rig.run_id
    assert observation.parameters[PARAM_CHECKOUT] == CHECKOUT
    assert observation.parameters[PARAM_CONTINUES] == rig.entry.id
    assert observation.parameters[PARAM_RESOLUTION] == "b-1"
    assert observation.parameters["pipeline"] == rig.entry.parameters["pipeline"]


def test_the_second_budget_check_cuts_off_before_anything_is_journaled(
    rig: Rig,
) -> None:
    rig.answer(rig.paused(offset=30))

    result = rig.acts.act(rig.resume(), budget_allowing(1), rig.faults)

    assert result is Acted.CUT_OFF
    assert len(rig.entries()) == 1


def test_a_continued_entry_that_is_gone_is_a_defect(rig: Rig) -> None:
    action = ResumeRun(
        rig.node.id,
        rig.run_id,
        "no-such",
        "b-1",
        Path(CHECKOUT),
        cause=ResumeCause.RESOLUTION,
    )

    with pytest.raises(ValueError, match="does not exist"):
        rig.acts.act(action, generous_budget(), rig.faults)


# -- the launch branch --------------------------------------------------------

INSTRUCTIONS = 'Address "only" the schema\nconcerns, é.'


def _resolved(rig: Rig, decision: str, instructions: str | None = None) -> str:
    return block_and_resolve(rig.store, rig.node, decision, instructions)


def _launch(
    rig: Rig,
    decision: str,
    instructions: str | None = None,
    journal_extra: dict[str, object] | None = None,
) -> Acted:
    resolution = _resolved(rig, decision, instructions)
    rig.answer(rig.paused())
    action = ResumeRun(
        rig.node.id,
        rig.run_id,
        rig.entry.id,
        resolution,
        Path(CHECKOUT),
        cause=ResumeCause.RESOLUTION,
        journal_extra=journal_extra or {},
    )
    return rig.acts.act(action, generous_budget(), rig.faults)


def test_a_resume_records_the_evidence_it_was_checked_on(rig: Rig) -> None:
    _launch(rig, "resume", None, {PARAM_DISPATCH_CHECK: {"branch": "main"}})

    continuation = rig.entries()[-1]
    assert continuation.parameters[PARAM_CONTINUATION] == "resume"
    assert continuation.parameters[PARAM_DISPATCH_CHECK] == {"branch": "main"}


def test_a_resume_passes_the_instructions_and_no_decision(rig: Rig) -> None:
    result = _launch(rig, "resume", INSTRUCTIONS)

    assert result is Acted.WROTE
    [argv] = rig.popen.argvs
    assert argv[1:] == ["run", "--resume", rig.run_id, "--instructions", INSTRUCTIONS]
    assert "--run-id" not in argv and "-p" not in argv and "P4" not in argv
    assert rig.popen.kwargs[0]["cwd"] == CHECKOUT


def test_a_resume_without_instructions_passes_none(rig: Rig) -> None:
    _launch(rig, "resume")

    [argv] = rig.popen.argvs
    assert "--instructions" not in argv and "--decision" not in argv


def test_the_entry_is_journaled_before_the_spawn_and_the_child_is_tracked(
    rig: Rig,
) -> None:
    _launch(rig, "resume")

    assert rig.popen.open_entries == [1]
    entry = rig.entries()[-1]
    assert not entry.is_resolved
    assert entry.parameters[PARAM_CONTINUATION] == "resume"
    assert rig.tracker.get(entry.id) is not None
    assert log_paths(rig.supervisor_dir, entry.id).stderr.exists()


def test_the_instructions_are_not_copied_into_the_journal(rig: Rig) -> None:
    _launch(rig, "resume", INSTRUCTIONS)

    entry = rig.entries()[-1]
    assert INSTRUCTIONS not in str(entry.parameters)


def test_a_spawn_error_blocks_with_spawn_error_and_launches_nothing(rig: Rig) -> None:
    rig.popen.error = FileNotFoundError("sq")

    result = _launch(rig, "resume")

    assert result is Acted.WROTE
    entry = rig.entries()[-1]
    assert entry.outcome is JournalOutcome.FAILED
    assert entry.result is not None
    assert entry.result[RESULT_RESUME_FAILURE] == "spawn_error"
    assert rig.tracker.get(entry.id) is None
    node = rig.store.get_node(rig.node.id)
    assert node is not None and node.status is NodeStatus.BLOCKED_ON_HUMAN


def test_a_resolution_resume_journals_its_cause(rig: Rig) -> None:
    _launch(rig, "resume")

    entry = rig.entries()[-1]
    assert entry.parameters[PARAM_RESUME_CAUSE] == ResumeCause.RESOLUTION.value


def _transient(rig: Rig, instructions: str | None) -> Acted:
    rig.answer(rig.paused())
    action = ResumeRun(
        rig.node.id,
        rig.run_id,
        rig.entry.id,
        None,
        Path(CHECKOUT),
        cause=ResumeCause.TRANSIENT,
        instructions=instructions,
    )
    return rig.acts.act(action, generous_budget(), rig.faults)


@pytest.mark.parametrize("instructions", [None, INSTRUCTIONS])
def test_a_transient_resume_journals_its_cause_and_names_no_resolution(
    rig: Rig, instructions: str | None
) -> None:
    assert _transient(rig, instructions) is Acted.WROTE

    entry = rig.entries()[-1]
    assert entry.parameters[PARAM_RESUME_CAUSE] == ResumeCause.TRANSIENT.value
    assert PARAM_RESOLUTION not in entry.parameters
    [argv] = rig.popen.argvs
    assert ("--instructions" in argv) is (instructions is not None)
