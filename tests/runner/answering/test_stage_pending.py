"""The stage's pending pass: decline or launch, oldest first, under the cap (D10)."""

from __future__ import annotations

from pathlib import Path

import pytest
from answerer_settings import answerer_settings
from sq_stub_scripts import check_reply, proposed_answer_reply

from amoeba.process import RunOutcome
from amoeba.runner.answering import stage as stage_module
from amoeba.runner.answering.stage import AnsweringStage
from amoeba.runner.faults import NodeContext, TickFaults
from amoeba.runner.project_config import AnswererSettings
from amoeba.store import (
    CommandKind,
    DeclineReason,
    QuestionRecord,
    QuestionState,
    Store,
)
from runner.answering.launch_rig import (
    budget,
    build_stage_rig,
    default_settings,
    run_document,
    write_replies,
)


def _state(store: Store, record: QuestionRecord) -> QuestionState:
    found = store.question(record.id)
    assert found is not None
    return found.state


def _settings(max_concurrent_runs: int = 2) -> AnswererSettings:
    return answerer_settings(
        rules_paths=default_settings().rules_paths,
        passages_max_chars=default_settings().passages_max_chars,
        max_concurrent_runs=max_concurrent_runs,
    )


def _answering(store: Store, project_id: str) -> int:
    return len(
        [
            e
            for e in store.unresolved_journal_entries(project_id)
            if e.kind is CommandKind.SQ_ANSWER
        ]
    )


def test_the_cap_holds_back_the_questions_over_it(store: Store, tmp_path: Path) -> None:
    rig = build_stage_rig(tmp_path, store, settings=_settings(2))
    records = [rig.launch.record, rig.launch.ask_another(1), rig.launch.ask_another(2)]

    rig.run()

    states = [_state(store, r) for r in records]
    assert states == [
        QuestionState.ANSWERING,
        QuestionState.ANSWERING,
        QuestionState.PENDING,
    ]
    assert _answering(store, records[0].project_id) == 2


def test_the_oldest_questions_launch_first(store: Store, tmp_path: Path) -> None:
    rig = build_stage_rig(tmp_path, store, settings=_settings(1))
    oldest = rig.launch.record
    rig.launch.ask_another(1)

    rig.run()

    assert _state(store, oldest) is QuestionState.ANSWERING


def test_a_finished_run_frees_its_slot_in_the_same_tick(
    store: Store, tmp_path: Path
) -> None:
    rig = build_stage_rig(tmp_path, store, settings=_settings(1))
    first = rig.launch.record
    entry = rig.start(first)
    waiting = rig.launch.ask_another(1)
    write_replies(
        entry, proposed_answer_reply("use main", ["P1"]), check_reply("yes", "ok")
    )
    rig.poll.answers.append(run_document(entry, RunOutcome.COMPLETED))

    rig.run()

    assert _state(store, first) is QuestionState.ANSWERED
    assert _state(store, waiting) is QuestionState.ANSWERING


def test_a_spent_budget_launches_nothing_but_still_declines(
    store: Store, tmp_path: Path
) -> None:
    rig = build_stage_rig(tmp_path, store, settings=_settings())
    launchable = rig.launch.record
    unanswerable = rig.launch.ask_another(1, question="")

    result = rig.run(allowed=0)

    assert result.cut_off
    assert rig.launch.popen.calls == []
    assert _state(store, launchable) is QuestionState.PENDING
    declined = store.question(unanswerable.id)
    assert declined is not None
    assert declined.decline_reason is DeclineReason.QUESTION_MISSING


def test_a_question_with_no_answerer_section_is_declined_and_never_launched(
    store: Store, tmp_path: Path
) -> None:
    rig = build_stage_rig(tmp_path, store)
    bare = AnsweringStage(
        store=store,
        project_id=rig.launch.context.project_id,
        launch=None,
        observer=rig.stage._observer,  # pyright: ignore[reportPrivateUsage]
        node_context=NodeContext(),
    )

    bare.run(budget(), TickFaults())

    declined = store.question(rig.launch.record.id)
    assert declined is not None
    assert declined.decline_reason is DeclineReason.ANSWERER_NOT_CONFIGURED
    assert rig.launch.popen.calls == []


def test_a_launch_fault_escalates_per_project_not_per_node(
    store: Store, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rig = build_stage_rig(tmp_path, store)
    seen: list[str | None] = []

    def exploding(*_args: object, **_kwargs: object) -> None:
        seen.append(rig.node_context.node_id)
        raise RuntimeError("launch exploded")

    monkeypatch.setattr(stage_module, "launch_answering", exploding)

    with pytest.raises(RuntimeError, match="launch exploded"):
        rig.run()

    assert seen == [None]


def test_a_finish_fault_escalates_per_project_not_per_node(
    store: Store, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rig = build_stage_rig(tmp_path, store)
    entry = rig.start(rig.launch.record)
    rig.poll.answers.append(run_document(entry, RunOutcome.FAILED))
    seen: list[str | None] = []

    def exploding(*_args: object, **_kwargs: object) -> None:
        seen.append(rig.node_context.node_id)
        raise RuntimeError("finish exploded")

    monkeypatch.setattr(stage_module, "finish_answering", exploding)

    with pytest.raises(RuntimeError, match="finish exploded"):
        rig.run()

    assert seen == [None]
