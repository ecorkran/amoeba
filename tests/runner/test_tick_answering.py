"""The answering stage in the project tick: declines, skips, and fault isolation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from answerer_settings import answerer_settings
from feed_harness import raw_changes
from question_harness import catch_for, make_slice, seed_question

from amoeba.process import RunOutcome
from amoeba.runner import tick as tick_module
from amoeba.runner.answering.stage import AnsweringStage, StageResult
from amoeba.runner.budget import TickBudget, TickResult
from amoeba.runner.faults import TickFaults
from amoeba.runner.project_config import ProjectSettings
from amoeba.store import (
    AnsweredBy,
    BlockedKind,
    CommandKind,
    DeclineReason,
    JournalOutcome,
    QuestionCatch,
    QuestionRecord,
    QuestionState,
    Store,
)
from amoeba.store.feed_models import ChangeKind
from runner.observe_support import Host
from runner.resolutions.resolution_support import (
    design_step,
    finished_run,
    paused_document,
    resolve_block,
)
from runner.tick_support import PROJECT, Rig, StoreHost, drive_project, tenant_for

LINK = "cf-1"
ANSWERER = answerer_settings()


@pytest.fixture
def rig(tmp_path: Path, store: Store) -> Rig:
    built = Rig(tmp_path, store)
    built.planners = ()
    return built


def _ask(
    store: Store,
    question: str | None = "which branch?",
    node_id: str | None = None,
) -> QuestionRecord:
    """A caught question: its block and its pending record, as ingest leaves them."""
    node_id = make_slice(store) if node_id is None else node_id
    catch = catch_for(store, node_id, question=question)
    record = store.record_question(catch, block_context="ctx", block_payload=None)
    # Ingest resolves the entry with the report; nothing is left to observe.
    store.journal_resolve(catch.source_entry_id, outcome=JournalOutcome.COMPLETED)
    return record


def _ask_on_a_paused_run(store: Store) -> QuestionRecord:
    """A question whose run is paused on it, so the PM's resume can be applied."""
    node = design_step(store)
    run_id = f"run-{node.id[:8]}"
    entry = finished_run(
        store,
        node,
        RunOutcome.PAUSED,
        document=paused_document(run_id, kind="agent_question"),
    )
    catch = QuestionCatch(
        project_id=PROJECT,
        node_id=node.id,
        source_entry_id=entry.id,
        run_id=run_id,
        step=None,
        question="which branch?",
        truncated=False,
    )
    return store.record_question(catch, block_context="ctx", block_payload=None)


def _reload(store: Store, record: QuestionRecord) -> QuestionRecord:
    found = store.question(record.id)
    assert found is not None
    return found


def _declines(store: Store) -> list[object]:
    return [
        c.payload["decline_reason"]
        for c in raw_changes(store, PROJECT)
        if c.kind is ChangeKind.QUESTION_STATE_CHANGED and c.payload["to"] == "declined"
    ]


def test_a_question_with_no_text_is_declined_question_missing(
    rig: Rig, store: Store
) -> None:
    record = _ask(store, question=None)

    result, tick = rig.tick()

    assert result is TickResult.COMPLETE and tick.wrote
    declined = _reload(store, record)
    assert declined.state is QuestionState.DECLINED
    assert declined.decline_reason is DeclineReason.QUESTION_MISSING


def test_no_answerer_section_declines_not_configured(rig: Rig, store: Store) -> None:
    record = _ask(store)

    rig.tick()

    assert (
        _reload(store, record).decline_reason is DeclineReason.ANSWERER_NOT_CONFIGURED
    )


def test_a_configured_answerer_still_declines_a_question_with_no_text(
    rig: Rig, store: Store
) -> None:
    rig.project_settings = ProjectSettings(pipeline="p456", answerer=ANSWERER)
    record = _ask(store, question=None)

    rig.tick()

    assert _reload(store, record).decline_reason is DeclineReason.QUESTION_MISSING


def test_a_pm_resolution_before_the_stage_is_skipped_then_answered_by_the_pm(
    rig: Rig, store: Store
) -> None:
    record = _ask_on_a_paused_run(store)
    block_id = record.blocked_state_id
    assert block_id is not None
    resolve_block(store, block_id, "resume", "use main")

    # The stage alone sees a resolution waiting for the Runner and leaves it.
    stage = AnsweringStage(
        store=store,
        project_id=PROJECT,
        launch=None,
        observer=rig.observer,
        node_context=rig.context,
    )
    budget = TickBudget(1_000.0, Host(), rig.clock.monotonic)
    assert stage.run(budget, TickFaults()).wrote is False
    assert _reload(store, record).state is QuestionState.PENDING

    rig.tick()

    answered = _reload(store, record)
    assert answered.state is QuestionState.ANSWERED
    assert answered.answered_by is AnsweredBy.PM
    assert answered.answer == "use main"
    assert _declines(store) == []


@pytest.mark.usefixtures("passing_checks")
def test_a_question_caught_in_a_cut_off_tick_is_still_declined(
    rig: Rig, store: Store
) -> None:
    record = _ask(store)
    design_step(store)
    drive_project(store)
    rig.planners = (rig.planner,)
    rig.deadline = 0.0

    result, _ = rig.tick()

    assert result is TickResult.CUT_OFF
    assert _reload(store, record).state is QuestionState.DECLINED


def test_a_broken_invariant_escalates_per_project_once(rig: Rig, store: Store) -> None:
    node_id = make_slice(store)
    block = store.block(node_id, kind=BlockedKind.HUMAN, context="q")
    # Resolved by the Runner's own write: nothing awaits the Runner.
    store.resolve(node_id, resolved_by="runner", detail="routed")
    record = seed_question(store, node_id, blocked_state_id=block.id)
    store.journal_resolve(record.source_entry_id, outcome=JournalOutcome.COMPLETED)

    tenant_for(rig).tick(StoreHost(store))
    tenant_for(rig).tick(StoreHost(store))

    [escalation] = store.open_project_escalations(PROJECT)
    assert "resolved and no resolution awaits" in str(escalation.payload)
    assert _reload(store, record).state is QuestionState.PENDING


# --------------------------------------------------------------------------
# The stage's place in the tick (slice 144, D10)
# --------------------------------------------------------------------------


def test_the_stage_runs_after_finished_runs_are_recorded(
    rig: Rig, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []
    real_record = tick_module.record_finished
    real_run = AnsweringStage.run

    def record(*args: Any, **kwargs: Any) -> Any:
        calls.append("record_finished")
        return real_record(*args, **kwargs)

    def run(self: AnsweringStage, *args: Any, **kwargs: Any) -> Any:
        calls.append("answering")
        return real_run(self, *args, **kwargs)

    monkeypatch.setattr(tick_module, "record_finished", record)
    monkeypatch.setattr(AnsweringStage, "run", run)

    rig.tick()

    assert calls == ["record_finished", "answering"]


def test_a_cut_off_stage_cuts_the_tick_off(
    rig: Rig, monkeypatch: pytest.MonkeyPatch
) -> None:
    def cut_off(self: AnsweringStage, *args: Any, **kwargs: Any) -> StageResult:
        return StageResult(True, False)

    monkeypatch.setattr(AnsweringStage, "run", cut_off)

    result, _ = rig.tick()

    assert result is TickResult.CUT_OFF


def test_an_sq_answer_entry_never_reaches_record_finished(
    rig: Rig, store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    node_id = make_slice(store)
    entry = store.journal_issue(
        node_id,
        kind=CommandKind.SQ_ANSWER,
        parameters={
            "run_id": "run-answer-1",
            "pipeline": "answering.yaml",
            "params": {},
            "scratch": "/tmp/answering/x",
        },
    )
    recorded: list[str] = []
    real_record = tick_module.record_finished

    def record(*args: Any, **kwargs: Any) -> Any:
        recorded.extend(run.run.entry.id for run in args[-1])
        return real_record(*args, **kwargs)

    monkeypatch.setattr(tick_module, "record_finished", record)

    rig.tick()

    assert entry.id not in recorded
    unresolved = store.journal_entry(entry.id)
    assert unresolved is not None and not unresolved.is_resolved


def test_no_answerer_section_journals_no_sq_answer(rig: Rig, store: Store) -> None:
    _ask(store)

    rig.tick()

    assert not [
        e for e in store.journal_entries(PROJECT) if e.kind is CommandKind.SQ_ANSWER
    ]
