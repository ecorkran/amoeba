"""``begin_answering``: one transaction for the entry and the state change (144)."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime

import pytest
from fault_injection import InjectedFailureError, fail_on_statement
from question_harness import (
    PROJECT,
    catch_for,
    make_slice,
    seed_question,
    submit_resolution,
)

from amoeba.runner.resolutions.vocabulary import ResolutionDecision
from amoeba.store import (
    AnsweredBy,
    AnsweringLaunch,
    BeginStatus,
    ChangeKind,
    CommandKind,
    JournalEntry,
    PassageRef,
    QuestionNotFoundError,
    QuestionRecord,
    QuestionState,
    ResolutionOutcome,
    Store,
    sql_questions,
)

RUN_ID = "run-20261103-answer-0001"
PARAMETERS: dict[str, object] = {
    "run_id": RUN_ID,
    "pipeline": "answering.yaml",
    "params": {"answer-model": "m1", "check-model": "m2"},
    "scratch": "/tmp/answering/run",
}
PASSAGES = (
    PassageRef("P1", "docs/rules.md", None, datetime(2026, 11, 1, tzinfo=UTC)),
    PassageRef("P2", "q-7", "q-7", datetime(2026, 10, 30, tzinfo=UTC)),
)


def _launch(
    node_id: str, parameters: Mapping[str, object] | None = None
) -> AnsweringLaunch:
    return AnsweringLaunch(
        node_id=node_id,
        run_id=RUN_ID,
        parameters=PARAMETERS if parameters is None else parameters,
        source_commit="abc123",
        passages=PASSAGES,
        dropped_pm_answers=("q-3",),
    )


def _ask(store: Store) -> tuple[str, QuestionRecord]:
    node_id = make_slice(store)
    record = store.record_question(
        catch_for(store, node_id), block_context="ctx", block_payload=None
    )
    return node_id, record


def _answering_entries(store: Store, node_id: str) -> list[JournalEntry]:
    return [
        entry
        for entry in store.journal_entries(PROJECT, node_id=node_id)
        if entry.kind is CommandKind.SQ_ANSWER
    ]


def test_begun_journals_the_entry_and_moves_the_record(store: Store) -> None:
    node_id, record = _ask(store)

    outcome = store.begin_answering(record.id, _launch(node_id))

    assert outcome.status is BeginStatus.BEGUN
    assert outcome.entry is not None and outcome.record is not None
    assert not outcome.entry.is_resolved
    assert set(outcome.entry.parameters) >= {"run_id", "pipeline", "params", "scratch"}
    assert outcome.record.state is QuestionState.ANSWERING
    assert outcome.record.answering_entry_id == outcome.entry.id
    assert outcome.record.source_commit == "abc123"
    assert outcome.record.dropped_pm_answers == ("q-3",)
    assert store.question(record.id) == outcome.record


def test_the_passage_index_is_stored_without_text(store: Store) -> None:
    node_id, record = _ask(store)

    outcome = store.begin_answering(record.id, _launch(node_id))

    assert outcome.record is not None
    assert outcome.record.passage_index == PASSAGES
    stored = store._execute(  # pyright: ignore[reportPrivateUsage]
        f"SELECT {sql_questions.COL_QUESTION_PASSAGE_INDEX}"
        f" FROM {sql_questions.TABLE_QUESTION_RECORDS} WHERE id = ?",
        (record.id,),
    ).fetchone()
    assert "text" not in stored[0]


def test_the_state_change_reaches_the_feed(store: Store) -> None:
    node_id, record = _ask(store)

    store.begin_answering(record.id, _launch(node_id))

    kinds = [change.kind for change in store.changes(PROJECT, limit=100)]
    assert kinds.count(ChangeKind.QUESTION_STATE_CHANGED) == 1


def test_settled_writes_nothing_when_the_pm_answered_first(store: Store) -> None:
    node_id, _ = _ask(store)
    answered = seed_question(
        store,
        node_id,
        state=QuestionState.ANSWERED,
        answered_by=AnsweredBy.PM,
        answer="dev",
    )

    outcome = store.begin_answering(answered.id, _launch(node_id))

    assert outcome.status is BeginStatus.SETTLED
    assert outcome.entry is None and outcome.record is None
    assert _answering_entries(store, node_id) == []
    assert store.question(answered.id) == answered


def test_block_resolved_writes_nothing(store: Store) -> None:
    node_id, record = _ask(store)
    assert record.blocked_state_id is not None
    submit_resolution(
        store,
        record.blocked_state_id,
        ResolutionDecision.RESUME.value,
        instructions="x",
    )

    outcome = store.begin_answering(record.id, _launch(node_id))

    assert outcome.status is BeginStatus.BLOCK_RESOLVED
    assert _answering_entries(store, node_id) == []
    assert store.question(record.id) == record


def test_a_missing_parameter_key_raises_before_any_write(store: Store) -> None:
    node_id, record = _ask(store)
    launch = _launch(node_id, {"run_id": RUN_ID, "pipeline": "p"})

    with pytest.raises(ValueError, match="requires parameter keys"):
        store.begin_answering(record.id, launch)

    assert _answering_entries(store, node_id) == []
    assert store.question(record.id) == record


def test_a_launch_for_another_node_raises(store: Store) -> None:
    _, record = _ask(store)

    with pytest.raises(ValueError, match="belongs to node"):
        store.begin_answering(record.id, _launch(make_slice(store)))


def test_an_unknown_id_raises(store: Store) -> None:
    with pytest.raises(QuestionNotFoundError):
        store.begin_answering("nope", _launch(make_slice(store)))


def test_a_failure_between_the_insert_and_the_state_update_leaves_nothing(
    store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    node_id, record = _ask(store)
    fail_on_statement(monkeypatch, store, sql_questions.UPDATE_QUESTION_BEGIN_ANSWERING)

    with pytest.raises(InjectedFailureError):
        store.begin_answering(record.id, _launch(node_id))

    monkeypatch.undo()
    assert _answering_entries(store, node_id) == []
    reloaded = store.question(record.id)
    assert reloaded is not None and reloaded.state is QuestionState.PENDING
    assert reloaded.answering_entry_id is None


def test_question_for_answering_entry(store: Store) -> None:
    node_id, record = _ask(store)
    outcome = store.begin_answering(record.id, _launch(node_id))
    assert outcome.entry is not None
    [source_entry] = [
        e
        for e in store.journal_entries(PROJECT, node_id=node_id)
        if e.kind is CommandKind.SQ_RUN
    ]

    linked = store.question_for_answering_entry(outcome.entry.id)

    assert linked is not None and linked.id == record.id
    assert store.question_for_answering_entry(source_entry.id) is None
    assert store.question_for_answering_entry("no-such-entry") is None


def test_a_pm_answer_to_an_answering_record_keeps_the_launch_columns(
    store: Store,
) -> None:
    node_id, record = _ask(store)
    begun = store.begin_answering(record.id, _launch(node_id)).record
    assert begun is not None and begun.blocked_state_id is not None
    submit_resolution(
        store,
        begun.blocked_state_id,
        ResolutionDecision.RESUME.value,
        instructions="pm",
    )

    store.acknowledge_resolution(
        begun.blocked_state_id, outcome=ResolutionOutcome.APPLIED
    )

    answered = store.question(record.id)
    assert answered is not None and answered.state is QuestionState.ANSWERED
    assert answered.answered_by is AnsweredBy.PM
    assert answered.answering_entry_id == begun.answering_entry_id
    assert answered.source_commit == "abc123"
    assert answered.passage_index == PASSAGES
