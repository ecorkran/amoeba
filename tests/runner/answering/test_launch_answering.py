"""``launch_answering``: the journal entry, the process and the failure paths (144)."""

from __future__ import annotations

from pathlib import Path

import pytest
from question_harness import submit_resolution

from amoeba.runner.answering.finish import RESULT_QUESTION_OUTCOME, QuestionOutcome
from amoeba.runner.answering.launch import LaunchStatus, launch_answering
from amoeba.store import (
    CommandKind,
    DeclineReason,
    JournalEntry,
    JournalOutcome,
    QuestionState,
    Store,
)
from runner.answering.launch_rig import RecordingPopen, budget, build_launch_rig


def _answer_entries(store: Store, project_id: str) -> list[JournalEntry]:
    return [
        e for e in store.journal_entries(project_id) if e.kind is CommandKind.SQ_ANSWER
    ]


def test_a_launch_journals_one_entry_links_the_record_and_starts_the_process(
    store: Store, tmp_path: Path
) -> None:
    rig = build_launch_rig(tmp_path, store)

    status = launch_answering(rig.context, rig.record, budget())

    [entry] = _answer_entries(store, rig.record.project_id)
    record = store.question(rig.record.id)
    assert status is LaunchStatus.STARTED
    assert not entry.is_resolved
    assert set(entry.parameters) >= {"run_id", "pipeline", "params", "scratch"}
    assert record is not None
    assert record.state is QuestionState.ANSWERING
    assert record.answering_entry_id == entry.id
    [(argv, cwd)] = rig.popen.calls
    assert cwd == entry.parameters["scratch"]
    assert entry.parameters["run_id"] in argv
    assert rig.context.tracker.get(entry.id) is not None


def test_a_spawn_failure_declines_launch_failed_and_resolves_the_entry(
    store: Store, tmp_path: Path
) -> None:
    rig = build_launch_rig(
        tmp_path, store, popen=RecordingPopen(OSError("sq is missing"))
    )

    status = launch_answering(rig.context, rig.record, budget())

    [entry] = _answer_entries(store, rig.record.project_id)
    record = store.question(rig.record.id)
    resolved = store.journal_entry(entry.id)
    assert status is LaunchStatus.DECLINED
    assert record is not None
    assert record.decline_reason is DeclineReason.ANSWERING_LAUNCH_FAILED
    assert "sq is missing" in (record.decline_detail or "")
    assert resolved is not None
    assert resolved.outcome is JournalOutcome.FAILED
    assert resolved.result is not None
    assert resolved.result[RESULT_QUESTION_OUTCOME] == QuestionOutcome.DECLINED.value
    assert rig.context.tracker.get(entry.id) is None
    assert store.pending_questions(rig.record.project_id) == []


def test_a_block_resolved_before_the_journal_starts_nothing(
    store: Store, tmp_path: Path
) -> None:
    rig = build_launch_rig(tmp_path, store)
    submit_resolution(
        store, rig.record.blocked_state_id or "", "resume", instructions="pm"
    )

    status = launch_answering(rig.context, rig.record, budget())

    assert status is LaunchStatus.SKIPPED
    assert _answer_entries(store, rig.record.project_id) == []
    assert rig.popen.calls == []
    assert store.question(rig.record.id) == rig.record


def test_a_question_the_pm_answered_first_starts_nothing(
    store: Store, tmp_path: Path
) -> None:
    rig = build_launch_rig(tmp_path, store)
    block_id = rig.record.blocked_state_id or ""
    submit_resolution(store, block_id, "resume", instructions="pm")
    from amoeba.store import ResolutionOutcome

    store.acknowledge_resolution(block_id, outcome=ResolutionOutcome.APPLIED)

    status = launch_answering(rig.context, rig.record, budget())

    assert status is LaunchStatus.SKIPPED
    assert rig.popen.calls == []
    assert _answer_entries(store, rig.record.project_id) == []


@pytest.mark.parametrize("launches", [1, 2])
def test_each_launch_gets_its_own_scratch_directory(
    store: Store, tmp_path: Path, launches: int
) -> None:
    rig = build_launch_rig(tmp_path, store)
    records = [rig.record, rig.ask_another()][:launches]

    for record in records:
        launch_answering(rig.context, record, budget())

    scratches = {cwd for _, cwd in rig.popen.calls}
    assert len(scratches) == launches
    assert all(Path(cwd).is_dir() for cwd in scratches)
