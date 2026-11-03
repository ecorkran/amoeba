"""The real stage with real models: plan passage and PM precedent (slice 144, D13).

One run per case from ``assemble_sources`` to the record's final state, against the
fixture repository and a throwaway store. A wrong result fails the test; nothing
retries and nothing is loosened to fit a model.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from live_settings import LiveSettings

from amoeba.store import AnsweredBy, DeclineReason, QuestionRecord, QuestionState, Store
from live.answering import question_tails as tails
from live.answering.stage_harness import LiveStage, build_live_stage

PM_DATE = datetime(2026, 11, 2, 12, 0, tzinfo=UTC)


def _answered_by_the_answerer(record: QuestionRecord) -> None:
    assert record.state is QuestionState.ANSWERED, (
        record.decline_reason,
        record.decline_detail,
        record.proposed_answer,
        record.check_reason,
    )
    assert record.answered_by is AnsweredBy.ANSWERER
    assert record.cited_passages
    assert record.check_verdict == "yes"


def _cites_the_pm_answer(record: QuestionRecord, pm: QuestionRecord) -> None:
    assert record.passage_index is not None and record.cited_passages is not None
    cited = {ref.id for ref in record.passage_index if ref.question_id == pm.id}
    assert cited & set(record.cited_passages), (record.cited_passages, pm.id)


def _stage(
    tmp_path: Path, store: Store, live_settings: LiveSettings, question: str
) -> LiveStage:
    return build_live_stage(tmp_path, store, live_settings, question)


def test_a_question_answered_by_a_rules_passage_is_answered(
    tmp_path: Path, store: Store, live_settings: LiveSettings
) -> None:
    live = _stage(tmp_path, store, live_settings, tails.PLAN_QUESTION)

    record = live.settle()

    _answered_by_the_answerer(record)
    block = store.blocked_state(record.blocked_state_id or "")
    assert block is not None and block.resolution is not None
    assert block.resolution.instructions


def test_a_reworded_question_on_the_same_slice_is_answered_from_the_pm_answer(
    tmp_path: Path, store: Store, live_settings: LiveSettings
) -> None:
    live = _stage(tmp_path, store, live_settings, tails.REWORDED_QUESTION)
    pm = live.seed_pm_answer(live.rig.node, tails.PM_QUESTION, tails.PM_ANSWER, PM_DATE)

    record = live.settle()

    _answered_by_the_answerer(record)
    _cites_the_pm_answer(record, pm)


def test_the_same_meaning_on_another_slice_is_answered_from_the_pm_answer(
    tmp_path: Path, store: Store, live_settings: LiveSettings
) -> None:
    live = _stage(tmp_path, store, live_settings, tails.REWORDED_QUESTION)
    elsewhere = live.rig.other_slice("Web Console", 1)
    pm = live.seed_pm_answer(
        elsewhere, tails.PM_QUESTION, tails.PM_ANSWER_FOR_EVERY_SLICE, PM_DATE
    )

    record = live.settle()

    _answered_by_the_answerer(record)
    _cites_the_pm_answer(record, pm)


def test_a_slice_where_the_answer_differs_is_declined(
    tmp_path: Path, store: Store, live_settings: LiveSettings
) -> None:
    live = _stage(tmp_path, store, live_settings, tails.PORT_QUESTION)
    elsewhere = live.rig.other_slice("Web Console", 1)
    live.seed_pm_answer(elsewhere, tails.PORT_QUESTION, tails.PORT_ANSWER, PM_DATE)

    record = live.settle()

    assert record.state is QuestionState.DECLINED, record.answer
    assert record.decline_reason in (
        DeclineReason.ANSWERER_DECLINED,
        DeclineReason.CHECK_SAID_NO,
    ), (record.decline_reason, record.decline_detail)
