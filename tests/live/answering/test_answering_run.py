"""``handle_pause`` on real pauses with real models: plan passage and PM precedent
(slice 223, task 9.3; restored from slice 144's stage test and rewritten).

One real pause per case, from the question to the record's final state, against the
fixture repository as a registered member. A wrong result fails the test; nothing
retries and nothing is loosened to fit a model.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from live_settings import LiveSettings

from live.answering import question_tails as tails
from live.answering.stage_harness import (
    OTHER_SLICE_LABEL,
    SLICE_LABEL,
    LivePause,
    Settled,
    build_live_pause,
)

PM_DATE = datetime(2026, 11, 2, 12, 0, tzinfo=UTC)
ANSWERED_AND_RESUMED = {"resumed", "not_delivered"}


def _answered_by_the_answerer(settled: Settled) -> None:
    assert settled.state == "answered", (
        settled.waiting_reason,
        settled.waiting_detail,
        settled.result,
    )
    assert settled.cited
    assert settled.verdict == "yes"
    assert settled.result["outcome"] in ANSWERED_AND_RESUMED, settled.result


def _cites_the_pm_answer(settled: Settled, pm_key: str) -> None:
    assert pm_key in settled.pm_passages, settled.pm_passages
    assert settled.pm_passages[pm_key] in settled.cited, (
        settled.cited,
        settled.pm_passages,
    )


def _pause(
    tmp_path: Path, amoeba_home: Path, live: LiveSettings, question: str
) -> LivePause:
    return build_live_pause(tmp_path, amoeba_home, live, question)


def test_a_question_answered_by_a_rules_passage_is_answered(
    tmp_path: Path, amoeba_home: Path, live_settings: LiveSettings
) -> None:
    live = _pause(tmp_path, amoeba_home, live_settings, tails.PLAN_QUESTION)

    settled = live.settle()

    _answered_by_the_answerer(settled)


def test_a_reworded_question_on_the_same_slice_is_answered_from_the_pm_answer(
    tmp_path: Path, amoeba_home: Path, live_settings: LiveSettings
) -> None:
    live = _pause(tmp_path, amoeba_home, live_settings, tails.REWORDED_QUESTION)
    pm = live.seed_pm_answer(SLICE_LABEL, tails.PM_QUESTION, tails.PM_ANSWER, PM_DATE)

    settled = live.settle()

    _answered_by_the_answerer(settled)
    _cites_the_pm_answer(settled, f"{pm.run_id}@{pm.paused_at}")


def test_the_same_meaning_on_another_slice_is_answered_from_the_pm_answer(
    tmp_path: Path, amoeba_home: Path, live_settings: LiveSettings
) -> None:
    live = _pause(tmp_path, amoeba_home, live_settings, tails.REWORDED_QUESTION)
    pm = live.seed_pm_answer(
        OTHER_SLICE_LABEL,
        tails.PM_QUESTION,
        tails.PM_ANSWER_FOR_EVERY_SLICE,
        PM_DATE,
    )

    settled = live.settle()

    _answered_by_the_answerer(settled)
    _cites_the_pm_answer(settled, f"{pm.run_id}@{pm.paused_at}")


def test_a_slice_where_the_answer_differs_waits_on_the_pm(
    tmp_path: Path, amoeba_home: Path, live_settings: LiveSettings
) -> None:
    live = _pause(tmp_path, amoeba_home, live_settings, tails.PORT_QUESTION)
    live.seed_pm_answer(
        OTHER_SLICE_LABEL, tails.PORT_QUESTION, tails.PORT_ANSWER, PM_DATE
    )

    settled = live.settle()

    assert settled.result["outcome"] == "waiting_on_pm", settled.result
    assert settled.state == "waiting_on_pm"
    assert settled.waiting_reason in ("answerer_declined", "check_said_no"), (
        settled.waiting_reason,
        settled.waiting_detail,
    )
