"""``submit_answer``: outcomes, the PM race, the run count, crash safety (slice 142)."""

from __future__ import annotations

import inspect
from dataclasses import replace
from functools import partial

import pytest
from fault_injection import InjectedFailureError, fail_on_statement
from question_harness import (
    PROJECT,
    catch_for,
    make_slice,
    seed_question,
    submit_resolution,
)

from amoeba.runner.answering.gate import evaluate_gate
from amoeba.runner.project_config import AnswererSettings
from amoeba.runner.resolutions.vocabulary import ResolutionDecision
from amoeba.store import (
    ANSWER_DECISION,
    AnsweredBy,
    AnswerGate,
    AnswerOutcome,
    AnswerSubmission,
    BlockedKind,
    BlockEffect,
    DeclineReason,
    GateRefusal,
    QuestionNotFoundError,
    QuestionRecord,
    QuestionState,
    ResolutionOutcome,
    Store,
    SubmissionKind,
    SubmissionOutcome,
    sql,
    sql_inbox,
    sql_questions,
)

QUESTION = "which branch?"
ANSWER = "use main"
INSTRUCTIONS = "You asked: which branch?\nAnswer: use main"
DETAIL = "answered by the answerer"
RESUME = ResolutionDecision.RESUME.value
RE_BLOCK = BlockEffect("resolution rejected", {"why": "test"})


def _pass(question: str, prior_answers: int) -> GateRefusal | None:
    return None


def _refusing(refusal: GateRefusal) -> AnswerGate:
    def gate(question: str, prior_answers: int) -> GateRefusal | None:
        return refusal

    return gate


class RecordingGate:
    """A passing gate that remembers what it was called with."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []

    def __call__(self, question: str, prior_answers: int) -> GateRefusal | None:
        self.calls.append((question, prior_answers))
        return None


def _ask(store: Store, *, run_id: str | None = None) -> tuple[str, QuestionRecord]:
    """A slice with a question block and its pending record."""
    node_id = make_slice(store)
    catch = catch_for(store, node_id, question=QUESTION)
    if run_id is not None:
        catch = replace(catch, run_id=run_id)
    record = store.record_question(catch, block_context="ctx", block_payload=None)
    return node_id, record


def _submit(
    store: Store,
    record: QuestionRecord,
    *,
    gate: AnswerGate = _pass,
    answer: str = ANSWER,
    instructions: str = INSTRUCTIONS,
    detail: str = DETAIL,
) -> AnswerSubmission:
    return store.submit_answer(
        record.id,
        answer=answer,
        instructions=instructions,
        detail=detail,
        gate=gate,
    )


def _reload(store: Store, record: QuestionRecord) -> QuestionRecord:
    found = store.question(record.id)
    assert found is not None
    return found


def _block_id(record: QuestionRecord) -> str:
    assert record.blocked_state_id is not None
    return record.blocked_state_id


def _assert_nothing_written(store: Store, node_id: str, record: QuestionRecord) -> None:
    """The slot is open, no submission row exists and the record is unchanged."""
    open_block = store.blocked_state_for(node_id)
    assert open_block is not None and not open_block.is_resolved
    assert open_block.id == _block_id(record)
    assert store.submissions(PROJECT) == []
    assert _reload(store, record) == record


# --------------------------------------------------------------------------
# Outcomes
# --------------------------------------------------------------------------


def test_submitted_fills_the_slot_writes_one_submission_and_answers_the_record(
    store: Store,
) -> None:
    node_id, record = _ask(store)

    result = _submit(store, record)

    assert result.outcome is AnswerOutcome.SUBMITTED
    block = store.blocked_state(_block_id(record))
    assert block is not None and block.resolution is not None
    assert block.resolution.decision == ANSWER_DECISION
    assert block.resolution.instructions == INSTRUCTIONS
    assert block.resolution.resolved_by == AnsweredBy.ANSWERER.value
    assert block.resolution.detail == DETAIL
    assert block.awaits_runner
    (submission,) = store.submissions(PROJECT)
    assert submission.kind is SubmissionKind.RESOLUTION
    assert submission.outcome is SubmissionOutcome.APPLIED
    assert submission.submitted_by == AnsweredBy.ANSWERER.value
    assert submission.payload["detail"] == DETAIL
    assert submission.payload["blocked_state_id"] == _block_id(record)
    assert result.record == _reload(store, record)
    assert result.record.state is QuestionState.ANSWERED
    assert result.record.answered_by is AnsweredBy.ANSWERER
    assert result.record.answer == ANSWER
    assert store.blocked_state_for(node_id) is None


@pytest.mark.parametrize(
    "refusal",
    [
        GateRefusal(DeclineReason.ANSWER_LIMIT_REACHED, None),
        GateRefusal(DeclineReason.RESERVED_TERM, "Force Push"),
    ],
    ids=["limit", "term"],
)
def test_declined_records_the_reason_and_leaves_the_slot_open(
    store: Store, refusal: GateRefusal
) -> None:
    node_id, record = _ask(store)

    result = _submit(store, record, gate=_refusing(refusal))

    assert result.outcome is AnswerOutcome.DECLINED
    assert result.record.state is QuestionState.DECLINED
    assert result.record.decline_reason is refusal.reason
    assert result.record.reserved_term == refusal.reserved_term
    assert result.record == _reload(store, record)
    open_block = store.blocked_state_for(node_id)
    assert open_block is not None and not open_block.is_resolved
    assert store.submissions(PROJECT) == []


def test_block_resolved_writes_nothing_when_the_pm_answered_first(
    store: Store,
) -> None:
    _, record = _ask(store)
    submit_resolution(store, _block_id(record), RESUME, instructions="pm says dev")
    gate = RecordingGate()

    result = _submit(store, record, gate=gate)

    assert result.outcome is AnswerOutcome.BLOCK_RESOLVED
    assert result.record == record
    assert gate.calls == []
    assert [s.submitted_by for s in store.submissions(PROJECT)] == ["pm"]


@pytest.mark.parametrize(
    ("state", "answered_by", "reason"),
    [
        (QuestionState.ANSWERED, AnsweredBy.ANSWERER, None),
        (QuestionState.ANSWERED, AnsweredBy.PM, None),
        (QuestionState.DECLINED, None, DeclineReason.NODE_ALREADY_BLOCKED),
        (QuestionState.DECLINED, None, DeclineReason.NO_ANSWER_ON_FILE),
    ],
    ids=["answered-answerer", "answered-pm", "declined-no-block", "declined"],
)
def test_settled_for_a_record_that_is_no_longer_open(
    store: Store,
    state: QuestionState,
    answered_by: AnsweredBy | None,
    reason: DeclineReason | None,
) -> None:
    record = seed_question(
        store,
        make_slice(store),
        state=state,
        answered_by=answered_by,
        answer="earlier" if answered_by is not None else None,
        decline_reason=reason,
    )
    gate = RecordingGate()

    result = _submit(store, record, gate=gate)

    assert result.outcome is AnswerOutcome.SETTLED
    assert result.record == record
    assert gate.calls == []
    assert store.submissions(PROJECT) == []


def test_an_unknown_id_raises(store: Store) -> None:
    with pytest.raises(QuestionNotFoundError):
        store.submit_answer(
            "nope", answer=ANSWER, instructions=INSTRUCTIONS, detail=DETAIL, gate=_pass
        )


@pytest.mark.parametrize("field", ["answer", "instructions", "detail"])
def test_a_blank_field_raises_and_writes_nothing(store: Store, field: str) -> None:
    node_id, record = _ask(store)
    fields = {"answer": ANSWER, "instructions": INSTRUCTIONS, "detail": DETAIL}
    fields[field] = "   "

    with pytest.raises(ValueError, match=field):
        store.submit_answer(
            record.id,
            gate=_pass,
            answer=fields["answer"],
            instructions=fields["instructions"],
            detail=fields["detail"],
        )

    _assert_nothing_written(store, node_id, record)


def test_a_record_with_no_question_text_raises(store: Store) -> None:
    record = seed_question(store, make_slice(store), question=None)

    with pytest.raises(ValueError, match="question text"):
        _submit(store, record)


def test_a_settled_record_with_no_question_text_settles_instead_of_raising(
    store: Store,
) -> None:
    record = seed_question(
        store,
        make_slice(store),
        state=QuestionState.DECLINED,
        decline_reason=DeclineReason.QUESTION_MISSING,
        question=None,
    )

    assert _submit(store, record).outcome is AnswerOutcome.SETTLED


def test_the_signature_takes_no_decision_or_submitter() -> None:
    parameters = set(inspect.signature(Store.submit_answer).parameters) - {"self"}

    assert parameters == {
        "question_id",
        "answer",
        "instructions",
        "detail",
        "gate",
        "evidence",
    }


def test_the_answer_decision_is_the_runners_resume() -> None:
    assert ANSWER_DECISION == ResolutionDecision.RESUME.value


# --------------------------------------------------------------------------
# Race, count and Runner rejection
# --------------------------------------------------------------------------


def test_race_pm_first_the_acknowledgment_records_the_pm_answer(store: Store) -> None:
    _, record = _ask(store)
    submit_resolution(store, _block_id(record), RESUME, instructions="pm says dev")
    assert _submit(store, record).outcome is AnswerOutcome.BLOCK_RESOLVED

    store.acknowledge_resolution(_block_id(record), outcome=ResolutionOutcome.APPLIED)

    settled = _reload(store, record)
    assert settled.state is QuestionState.ANSWERED
    assert settled.answered_by is AnsweredBy.PM
    assert settled.answer == "pm says dev"


def test_race_answerer_first_the_pm_resolution_is_rejected(store: Store) -> None:
    _, record = _ask(store)
    assert _submit(store, record).outcome is AnswerOutcome.SUBMITTED

    submit_resolution(store, _block_id(record), RESUME, instructions="pm says dev")

    (rejected,) = store.submissions(PROJECT, outcome=SubmissionOutcome.REJECTED)
    assert rejected.reason is not None and "already resolved" in rejected.reason
    kept = _reload(store, record)
    assert kept.answered_by is AnsweredBy.ANSWERER
    assert kept.answer == ANSWER


def test_count_prior_answers_grow_by_one_per_submission_and_a_replay_settles(
    store: Store,
) -> None:
    _, first = _ask(store)
    _, second = _ask(store)
    _, third = _ask(store)
    gate = RecordingGate()

    _submit(store, first, gate=gate)
    _submit(store, second, gate=gate)
    replay = _submit(store, first, gate=gate)
    _submit(store, third, gate=gate)

    assert replay.outcome is AnswerOutcome.SETTLED
    assert [prior for _, prior in gate.calls] == [0, 1, 2]


def test_count_only_the_answerers_answers_on_this_run_count(store: Store) -> None:
    node_id = make_slice(store)
    seed_question(
        store,
        node_id,
        state=QuestionState.ANSWERED,
        answered_by=AnsweredBy.PM,
        answer="pm",
    )
    seed_question(
        store,
        node_id,
        state=QuestionState.DECLINED,
        decline_reason=DeclineReason.NO_ANSWER_ON_FILE,
    )
    seed_question(store, node_id)
    seed_question(
        store,
        node_id,
        state=QuestionState.ANSWERED,
        answered_by=AnsweredBy.ANSWERER,
        answer="other run",
        project_id="other-project",
    )
    _, record = _ask(store)
    gate = RecordingGate()

    _submit(store, record, gate=gate)

    assert gate.calls == [(QUESTION, 0)]


def test_count_a_different_run_does_not_count(store: Store) -> None:
    _, earlier = _ask(store, run_id="run-a")
    _submit(store, earlier)
    _, later = _ask(store, run_id="run-b")
    gate = RecordingGate()

    _submit(store, later, gate=gate)

    assert gate.calls == [(QUESTION, 0)]


def test_count_the_limit_declines_the_third_answer_and_keeps_the_block_open(
    store: Store,
) -> None:
    gate = partial(
        evaluate_gate,
        answer=ANSWER,
        settings=AnswererSettings(
            answer_limit=2, reserved_terms=(), rules_paths=(), passages_max_chars=1000
        ),
    )
    for _ in range(2):
        seed_question(
            store,
            make_slice(store),
            state=QuestionState.ANSWERED,
            answered_by=AnsweredBy.ANSWERER,
            answer="earlier",
        )
    node_id, record = _ask(store)

    result = _submit(store, record, gate=gate)

    assert result.outcome is AnswerOutcome.DECLINED
    assert result.record.decline_reason is DeclineReason.ANSWER_LIMIT_REACHED
    open_block = store.blocked_state_for(node_id)
    assert open_block is not None and not open_block.is_resolved
    assert open_block.kind is BlockedKind.HUMAN
    assert store.submissions(PROJECT) == []


def test_rejected_by_the_runner_the_answer_counts_and_the_retry_is_no_precedent(
    store: Store,
) -> None:
    node_id, record = _ask(store)
    _submit(store, record)
    code = "instructions_not_applicable"

    store.acknowledge_resolution(
        _block_id(record),
        outcome=ResolutionOutcome.REJECTED,
        code=code,
        reason="the run cannot take instructions",
        effect=RE_BLOCK,
    )

    kept = _reload(store, record)
    assert kept.state is QuestionState.ANSWERED
    assert kept.answered_by is AnsweredBy.ANSWERER
    rejected_block = store.blocked_state(_block_id(record))
    assert rejected_block is not None and rejected_block.runner_code == code
    new_block = store.blocked_state_for(node_id)
    assert new_block is not None and new_block.id != _block_id(record)
    assert new_block.kind is BlockedKind.HUMAN
    gate = RecordingGate()
    _, next_record = _ask(store)
    _submit(store, next_record, gate=gate)
    assert gate.calls == [(QUESTION, 1)]
    submit_resolution(store, new_block.id, RESUME, instructions="pm retry")
    store.acknowledge_resolution(new_block.id, outcome=ResolutionOutcome.APPLIED)
    assert store.question_for_block(new_block.id) is None
    assert _reload(store, record) == kept


# --------------------------------------------------------------------------
# Crash safety
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "statement",
    [
        sql.FILL_RESOLUTION_SLOT,
        sql_inbox.INSERT_SUBMISSION,
        sql_questions.UPDATE_QUESTION_ANSWERED,
    ],
    ids=["slot", "submission", "record"],
)
def test_crash_in_any_write_leaves_nothing_behind(
    store: Store, monkeypatch: pytest.MonkeyPatch, statement: str
) -> None:
    node_id, record = _ask(store)
    fail_on_statement(monkeypatch, store, statement)

    with pytest.raises(InjectedFailureError):
        _submit(store, record)

    _assert_nothing_written(store, node_id, record)


def test_crash_in_the_gate_rolls_back_and_the_exception_propagates(
    store: Store,
) -> None:
    node_id, record = _ask(store)

    def exploding(question: str, prior_answers: int) -> GateRefusal | None:
        raise RuntimeError("gate blew up")

    with pytest.raises(RuntimeError, match="gate blew up"):
        _submit(store, record, gate=exploding)

    _assert_nothing_written(store, node_id, record)
