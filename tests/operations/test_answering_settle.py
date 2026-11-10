"""Settling a claim and the composed answering step (slice 223, tasks 5.8, 5.9)."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from fake_sq import COMPLETED, PAUSED_AGENT_QUESTION, poll_result
from store.question_support import (
    ANSWERING_RUN,
    KEY,
    NOW,
    claimed_question,
    seed_members,
)
from user_configs import user_config

from amoeba.answering.decide import Declined
from amoeba.answering.settings import AnswererSettings
from amoeba.answering.values import (
    AnsweredBy,
    AnsweringEvidence,
    DeclineReason,
    PassageRef,
)
from amoeba.operations.answering_run import Claim, scratch_path
from amoeba.operations.answering_settle import (
    Answered,
    Superseded,
    Waiting,
    answer_claim,
    settle,
)
from amoeba.operations.member_answering import answering_for
from amoeba.store.answers import add_pm_answer, answers_of, settle_answered
from amoeba.store.models import MemberSettings, QuestionKey
from amoeba.store.questions import get_question, insert_question
from amoeba.store.store import Store
from amoeba.store.vocabulary import QuestionState
from amoeba.upstream.squadron.run_outcome import RunEnded
from operations.pause_support import FakeChild, build_deps

QUESTION_TEXT = "What is the maximum length of a source file?"
SETTINGS = AnswererSettings(
    answer_limit=3,
    reserved_terms=(),
    rules_paths=("CLAUDE.md",),
    passages_max_chars=1000,
    answer_model="a",
    check_model="c",
    max_cost_usd=0.5,
)
CITED = PassageRef(id="P1", source="CLAUDE.md", question_id=None, date=NOW)


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    with Store.open(tmp_path / "amoeba.sqlite3") as opened:
        seed_members(opened)
        with opened.write() as transaction:
            insert_question(transaction, claimed_question(), now=NOW)
        yield opened


def _claim(settings: AnswererSettings = SETTINGS) -> Claim:
    return Claim(
        key=KEY,
        answering_run_id=ANSWERING_RUN,
        question=QUESTION_TEXT,
        passage_ids=frozenset({"P1"}),
        settings=settings,
        wait_seconds=30,
    )


def _write_replies(
    tmp_path: Path,
    *,
    answer: dict[str, object] | None,
    check: dict[str, object] | None,
) -> None:
    scratch = scratch_path(tmp_path / "answering", ANSWERING_RUN)
    scratch.mkdir(parents=True)
    for name, content in (("answer.json", answer), ("check.json", check)):
        if content is not None:
            (scratch / name).write_text(json.dumps(content), encoding="utf-8")


def _proposed(text: str = "Keep files near 300 lines.") -> dict[str, object]:
    return {"kind": "answer", "answer": text, "cited": ["P1"]}


YES: dict[str, object] = {"verdict": "yes", "reason": "settled by CLAUDE.md"}
NO: dict[str, object] = {"verdict": "no", "reason": "the rule is older"}


def _completed() -> RunEnded:
    return RunEnded(poll_result(COMPLETED, ANSWERING_RUN))


def _state(store: Store) -> tuple[QuestionState, DeclineReason | None]:
    with store.read() as transaction:
        record = get_question(transaction, KEY)
    assert record is not None
    return record.state, record.waiting_reason


def test_a_confirmed_answer_through_the_gate_is_answered_with_its_citations(
    store: Store, tmp_path: Path
) -> None:
    _write_replies(tmp_path, answer=_proposed(), check=YES)
    rig = build_deps(tmp_path, polls={}, spawns=[])

    result = settle(store, rig.deps, _claim(), _completed())

    assert isinstance(result, Answered)
    assert result.answer == "Keep files near 300 lines."
    with store.read() as transaction:
        rows = answers_of(transaction, KEY)
        record = get_question(transaction, KEY)
    assert [(r.answered_by, r.cited) for r in rows] == [(AnsweredBy.ANSWERER, ("P1",))]
    assert rows[0].seq == result.answer_seq
    assert record is not None
    assert record.state is QuestionState.ANSWERED
    assert record.evidence == AnsweringEvidence(
        proposed_answer="Keep files near 300 lines.",
        cited=("P1",),
        verdict="yes",
        reason="settled by CLAUDE.md",
    )


def test_a_check_that_said_no_waits_on_the_pm_with_its_evidence(
    store: Store, tmp_path: Path
) -> None:
    _write_replies(tmp_path, answer=_proposed(), check=NO)
    rig = build_deps(tmp_path, polls={}, spawns=[])

    result = settle(store, rig.deps, _claim(), _completed())

    assert result == Waiting(DeclineReason.CHECK_SAID_NO, "the rule is older")
    assert _state(store) == (QuestionState.WAITING_ON_PM, DeclineReason.CHECK_SAID_NO)
    with store.read() as transaction:
        record = get_question(transaction, KEY)
        assert answers_of(transaction, KEY) == ()
    assert record is not None
    assert record.evidence is not None
    assert record.evidence.verdict == "no"
    assert record.waiting_detail == "the rule is older"


def test_a_screen_refusal_waits_with_reserved_term(
    store: Store, tmp_path: Path
) -> None:
    _write_replies(tmp_path, answer=_proposed("Then git push to origin."), check=YES)
    rig = build_deps(tmp_path, polls={}, spawns=[])
    screened = SETTINGS.model_copy(update={"reserved_terms": ("git push",)})

    result = settle(store, rig.deps, _claim(screened), _completed())

    assert isinstance(result, Waiting)
    assert result.reason is DeclineReason.RESERVED_TERM
    assert "git push" in result.detail
    assert _state(store)[0] is QuestionState.WAITING_ON_PM
    with store.read() as transaction:
        assert answers_of(transaction, KEY) == ()


def _settings_of(allow: tuple[str, ...]) -> AnswererSettings:
    member = MemberSettings(
        project_id="m",
        rules_paths=("CLAUDE.md",),
        authorize_allow=allow,
        authorize_deny=(),
    )
    return answering_for(member, user_config()).settings


def test_an_item_barred_for_one_member_and_allowed_for_another_differs(
    tmp_path: Path,
) -> None:
    outcomes: list[object] = []
    for index, allow in enumerate([(), ("push",)]):
        directory = tmp_path / f"case-{index}"
        with Store.open(directory / "amoeba.sqlite3") as store:
            seed_members(store)
            with store.write() as transaction:
                insert_question(transaction, claimed_question(), now=NOW)
            _write_replies(
                directory, answer=_proposed("Fine: run git push origin."), check=YES
            )
            rig = build_deps(directory, polls={}, spawns=[])
            outcomes.append(
                settle(store, rig.deps, _claim(_settings_of(allow)), _completed())
            )

    barred, allowed = outcomes
    assert isinstance(barred, Waiting)
    assert barred.reason is DeclineReason.RESERVED_TERM
    assert isinstance(allowed, Answered)


def test_a_pm_answer_during_settling_makes_it_superseded(
    store: Store, tmp_path: Path
) -> None:
    _write_replies(tmp_path, answer=_proposed(), check=YES)
    rig = build_deps(tmp_path, polls={}, spawns=[])
    with store.write() as transaction:
        add_pm_answer(transaction, KEY, "PM says 250.", now=NOW)

    result = settle(store, rig.deps, _claim(), _completed())

    assert result == Superseded()
    with store.read() as transaction:
        assert [r.answered_by for r in answers_of(transaction, KEY)] == [AnsweredBy.PM]


def test_a_declined_start_or_wait_settles_waiting_and_a_pm_answer_still_wins(
    store: Store, tmp_path: Path
) -> None:
    rig = build_deps(tmp_path, polls={}, spawns=[])
    stalled = Declined(
        DeclineReason.ANSWERING_RUN_STALLED,
        "no result after 30 seconds",
        AnsweringEvidence(),
    )

    first = settle(store, rig.deps, _claim(), stalled)
    second = settle(store, rig.deps, _claim(), stalled)

    assert first == Waiting(
        DeclineReason.ANSWERING_RUN_STALLED, "no result after 30 seconds"
    )
    assert second == Superseded()  # no longer claimed: a late reply is ignored


def test_a_run_that_failed_waits_with_answering_run_failed(
    store: Store, tmp_path: Path
) -> None:
    rig = build_deps(tmp_path, polls={}, spawns=[])
    failed = RunEnded(poll_result(PAUSED_AGENT_QUESTION, ANSWERING_RUN))

    result = settle(store, rig.deps, _claim(), failed)

    assert isinstance(result, Waiting)
    assert result.reason is DeclineReason.ANSWERING_RUN_FAILED
    assert "paused" in result.detail


def test_a_completed_run_with_no_answer_file_is_artifact_missing(
    store: Store, tmp_path: Path
) -> None:
    _write_replies(tmp_path, answer=None, check=None)
    rig = build_deps(tmp_path, polls={}, spawns=[])

    result = settle(store, rig.deps, _claim(), _completed())

    assert isinstance(result, Waiting)
    assert result.reason is DeclineReason.ARTIFACT_MISSING


def _prior_automatic_answers(store: Store, count: int) -> None:
    with store.write() as transaction:
        for number in range(count):
            key = QuestionKey(KEY.run_id, f"2026-11-10T0{number}:00:00+00:00")
            insert_question(
                transaction,
                claimed_question(key, answering_run_id=f"earlier-{number}"),
                now=NOW,
            )
    for number in range(count):
        key = QuestionKey(KEY.run_id, f"2026-11-10T0{number}:00:00+00:00")
        settle_answered(
            store,
            key,
            f"earlier-{number}",
            answer="x",
            cited=(),
            evidence=AnsweringEvidence(),
            gate=lambda _prior: None,
            now=NOW,
        )


def test_the_answer_limit_counts_automatic_answers_only(
    store: Store, tmp_path: Path
) -> None:
    _prior_automatic_answers(store, 2)
    with store.write() as transaction:
        for number in range(5):
            key = QuestionKey(KEY.run_id, f"2026-11-09T1{number}:00:00+00:00")
            insert_question(
                transaction,
                claimed_question(key, answering_run_id=f"pm-claim-{number}"),
                now=NOW,
            )
            add_pm_answer(transaction, key, "pm", now=NOW)
    _write_replies(tmp_path, answer=_proposed(), check=YES)
    rig = build_deps(tmp_path, polls={}, spawns=[])

    result = settle(store, rig.deps, _claim(), _completed())

    assert isinstance(result, Answered)


def test_at_the_answer_limit_the_gate_declines_and_nothing_is_written_for_the_answer(
    store: Store, tmp_path: Path
) -> None:
    _prior_automatic_answers(store, 3)
    _write_replies(tmp_path, answer=_proposed(), check=YES)
    rig = build_deps(tmp_path, polls={}, spawns=[])
    with store.read() as transaction:
        before = answers_of(transaction, KEY)

    result = settle(store, rig.deps, _claim(), _completed())

    assert isinstance(result, Waiting)
    assert result.reason is DeclineReason.ANSWER_LIMIT_REACHED
    with store.read() as transaction:
        assert answers_of(transaction, KEY) == before == ()
    assert _state(store) == (
        QuestionState.WAITING_ON_PM,
        DeclineReason.ANSWER_LIMIT_REACHED,
    )


def test_answer_claim_starts_waits_and_settles_with_no_transaction_open(
    store: Store, tmp_path: Path
) -> None:
    _write_replies(tmp_path, answer=_proposed(), check=YES)
    completed = poll_result(COMPLETED, ANSWERING_RUN)

    def assert_store_is_free() -> None:
        # A second write would fail if a transaction were open on this connection.
        with store.write():
            pass

    rig = build_deps(
        tmp_path,
        polls={ANSWERING_RUN: [completed]},
        spawns=[FakeChild(exit_code=0)],
        on_spawn=assert_store_is_free,
        on_poll=assert_store_is_free,
    )

    result = answer_claim(store, rig.deps, _claim())

    assert isinstance(result, Answered)
    (call,) = rig.spawner.calls
    assert call.cwd == scratch_path(tmp_path / "answering", ANSWERING_RUN)
    assert rig.poller.calls == [ANSWERING_RUN]
