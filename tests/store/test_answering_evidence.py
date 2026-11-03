"""Detail and evidence on ``decline_question`` and ``submit_answer`` (slice 144, D9)."""

from __future__ import annotations

import pytest
from fault_injection import InjectedFailureError, fail_on_statement
from question_harness import catch_for, make_slice, seed_question, submit_resolution

from amoeba.runner.resolutions.vocabulary import ResolutionDecision
from amoeba.store import (
    AnsweredBy,
    AnswerGate,
    AnsweringEvidence,
    AnswerOutcome,
    DeclineReason,
    GateRefusal,
    QuestionRecord,
    QuestionState,
    ResolutionOutcome,
    Store,
    sql_questions,
)
from amoeba.store.mapping_questions import encode_text_list

EVIDENCE = AnsweringEvidence(
    proposed_answer="use main",
    cited=("P1", "P2"),
    verdict="yes",
    reason="matches P1",
)
RESUME = ResolutionDecision.RESUME.value


def _ask(store: Store) -> QuestionRecord:
    node_id = make_slice(store)
    return store.record_question(
        catch_for(store, node_id), block_context="ctx", block_payload=None
    )


def _pass(question: str, prior_answers: int) -> GateRefusal | None:
    return None


def _refuse(question: str, prior_answers: int) -> GateRefusal | None:
    return GateRefusal(DeclineReason.ANSWER_LIMIT_REACHED, None)


def _submit(store: Store, record: QuestionRecord, gate: AnswerGate) -> AnswerOutcome:
    return store.submit_answer(
        record.id,
        answer="use main",
        instructions="You asked: x\nAnswer: use main",
        detail="by the answerer",
        gate=gate,
        evidence=EVIDENCE,
    ).outcome


def test_a_decline_with_detail_and_evidence_stores_every_field(store: Store) -> None:
    record = _ask(store)

    declined = store.decline_question(
        record.id,
        reason=DeclineReason.CHECK_SAID_NO,
        detail="the check disagreed",
        evidence=EVIDENCE,
    )

    assert declined.state is QuestionState.DECLINED
    assert declined.decline_reason is DeclineReason.CHECK_SAID_NO
    assert declined.decline_detail == "the check disagreed"
    assert declined.proposed_answer == "use main"
    assert declined.cited_passages == ("P1", "P2")
    assert declined.check_verdict == "yes"
    assert declined.check_reason == "matches P1"


def test_a_decline_with_neither_leaves_the_columns_null(store: Store) -> None:
    record = _ask(store)

    declined = store.decline_question(record.id, reason=DeclineReason.UNCITED)

    assert declined.decline_detail is None
    assert declined.proposed_answer is None
    assert declined.cited_passages is None
    assert declined.check_verdict is None


def test_partial_evidence_leaves_the_rest_null(store: Store) -> None:
    record = _ask(store)

    declined = store.decline_question(
        record.id,
        reason=DeclineReason.ARTIFACT_MALFORMED,
        evidence=AnsweringEvidence(proposed_answer="x"),
    )

    assert declined.proposed_answer == "x"
    assert declined.cited_passages is None
    assert declined.check_verdict is None


def test_a_failed_evidence_write_rolls_the_decline_back(
    store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    record = _ask(store)
    fail_on_statement(monkeypatch, store, sql_questions.UPDATE_QUESTION_EVIDENCE)

    with pytest.raises(InjectedFailureError):
        store.decline_question(
            record.id, reason=DeclineReason.CHECK_SAID_NO, evidence=EVIDENCE
        )

    monkeypatch.undo()
    assert store.question(record.id) == record


def test_a_submitted_answer_stores_the_evidence_beside_the_answer(
    store: Store,
) -> None:
    record = _ask(store)

    assert _submit(store, record, _pass) is AnswerOutcome.SUBMITTED

    answered = store.question(record.id)
    assert answered is not None
    assert answered.state is QuestionState.ANSWERED
    assert answered.answer == "use main"
    assert answered.cited_passages == ("P1", "P2")
    assert answered.check_verdict == "yes"
    assert answered.decline_detail is None


def test_a_gate_decline_also_stores_the_evidence(store: Store) -> None:
    record = _ask(store)

    assert _submit(store, record, _refuse) is AnswerOutcome.DECLINED

    declined = store.question(record.id)
    assert declined is not None
    assert declined.decline_reason is DeclineReason.ANSWER_LIMIT_REACHED
    assert declined.proposed_answer == "use main"
    assert declined.cited_passages == ("P1", "P2")


def test_a_block_resolved_submission_writes_no_evidence(store: Store) -> None:
    record = _ask(store)
    assert record.blocked_state_id is not None
    submit_resolution(store, record.blocked_state_id, RESUME, instructions="pm")

    assert _submit(store, record, _pass) is AnswerOutcome.BLOCK_RESOLVED

    assert store.question(record.id) == record


def test_a_pm_answer_to_a_declined_record_keeps_the_evidence(store: Store) -> None:
    record = _ask(store)
    declined = store.decline_question(
        record.id,
        reason=DeclineReason.CHECK_SAID_NO,
        detail="the check disagreed",
        evidence=EVIDENCE,
    )
    assert declined.blocked_state_id is not None
    submit_resolution(store, declined.blocked_state_id, RESUME, instructions="pm")

    store.acknowledge_resolution(
        declined.blocked_state_id, outcome=ResolutionOutcome.APPLIED
    )

    answered = store.question(record.id)
    assert answered is not None
    assert answered.answered_by is AnsweredBy.PM
    assert answered.decline_detail == "the check disagreed"
    assert answered.proposed_answer == "use main"
    assert answered.cited_passages == ("P1", "P2")
    assert answered.check_verdict == "yes"


def test_a_decline_with_only_a_detail_keeps_the_evidence_already_on_the_record(
    store: Store,
) -> None:
    seeded = seed_question(
        store,
        make_slice(store),
        answering={
            sql_questions.COL_QUESTION_PROPOSED_ANSWER: "use main",
            sql_questions.COL_QUESTION_CITED_PASSAGES: encode_text_list(("P1",)),
            sql_questions.COL_QUESTION_CHECK_VERDICT: "yes",
            sql_questions.COL_QUESTION_CHECK_REASON: "ok",
        },
    )

    declined = store.decline_question(
        seeded.id, reason=DeclineReason.ANSWERING_RUN_FAILED, detail="late news"
    )

    assert declined.decline_detail == "late news"
    assert declined.proposed_answer == "use main"
    assert declined.cited_passages == ("P1",)
    assert declined.check_verdict == "yes"
    assert declined.check_reason == "ok"
