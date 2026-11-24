"""``pause_begin``: each reply shape, the machine scope of its sweep and the stale
flag (slice 262, 4.4)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path

import pytest
from store.question_support import (
    ANSWERING_RUN,
    KEY,
    MEMBER_ID,
    NOW,
    claimed_question,
    insert_held_row,
    seed_members,
    waiting_question,
)
from store.seed import insert_checkout
from store_open import open_local_store
from user_configs import user_config

from amoeba.operations.errors import MALFORMED_CALL, CallRefused
from amoeba.operations.here_document import HereCaller, HereNotAProject
from amoeba.operations.pause_models import SkipReason
from amoeba.operations.steps.dispatch import StepEdges
from amoeba.operations.steps.limits import pause_claim_seconds
from amoeba.operations.steps.models import PAUSE_BEGIN
from amoeba.operations.steps.models_pause import (
    FateFields,
    PauseBeginReply,
    PauseBeginRequest,
)
from amoeba.operations.store_steps import LocalSteps
from amoeba.store.machines import invite_machine
from amoeba.store.messages import insert_request
from amoeba.store.models import QuestionKey
from amoeba.store.questions import get_question, insert_question
from amoeba.store.store import Store
from amoeba.store.vocabulary import ClosedReason, QuestionState, RequestState

CONFIG = user_config()
CF_ID = "cf-member-a"
QUESTION = "Which limit applies?"


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    with open_local_store(tmp_path / "amoeba.sqlite3") as opened:
        seed_members(opened)
        with opened.write() as transaction:
            insert_checkout(
                transaction,
                member_id=MEMBER_ID,
                cf_project_id=CF_ID,
                path="/work/a",
                now=NOW,
            )
        yield opened


def _begin(
    store: Store,
    *,
    at: timedelta = timedelta(0),
    **fields: object,
) -> PauseBeginReply:
    base: dict[str, object] = {
        "run_id": KEY.run_id,
        "here": HereCaller(project_id=CF_ID),
        "outcome": "paused",
        "paused": True,
        "checkpoint_kind": "agent_question",
        "paused_at": KEY.paused_at,
        "question": QUESTION,
        "fate": None,
    }
    steps = LocalSteps(store, StepEdges(lambda: NOW + at, lambda: CONFIG))
    return steps.run(PAUSE_BEGIN, PauseBeginRequest.model_validate({**base, **fields}))


def test_a_run_that_is_not_paused_is_skipped_with_no_caller_needed(
    store: Store,
) -> None:
    reply = _begin(store, here=None, paused=False, outcome="completed")

    assert reply.skip is SkipReason.NOT_PAUSED
    assert reply.skip_detail == "the run's outcome is completed"
    assert reply.member is None


def test_another_checkpoint_kind_and_a_missing_question_text_are_skipped(
    store: Store,
) -> None:
    other = _begin(store, here=None, checkpoint_kind="usage_limit")
    bare = _begin(store, here=None, question="  ")

    assert other.skip is SkipReason.NOT_AGENT_QUESTION
    assert other.skip_detail == "checkpoint kind usage_limit"
    assert bare.skip is SkipReason.NO_QUESTION_TEXT


def test_an_answering_runs_own_pause_is_skipped(store: Store) -> None:
    with store.write() as transaction:
        insert_question(transaction, claimed_question(), now=NOW)

    reply = _begin(store, run_id=ANSWERING_RUN)

    assert reply.skip is SkipReason.ANSWERING_RUN


def test_a_request_with_no_caller_past_the_run_skips_is_malformed(
    store: Store,
) -> None:
    with pytest.raises(CallRefused) as raised:
        _begin(store, here=None)

    assert raised.value.code == MALFORMED_CALL


def test_not_a_project_is_a_skip_and_not_in_program_is_returned(store: Store) -> None:
    nowhere = _begin(store, here=HereNotAProject(not_a_project="no project here"))
    unknown = _begin(store, here=HereCaller(project_id="cf-unknown"))

    assert nowhere.skip is SkipReason.NOT_A_PROJECT
    assert nowhere.skip_detail == "no project here"
    assert unknown.not_in_program == "cf-unknown"
    assert unknown.skip is None


def test_no_row_returns_the_member_its_settings_the_limit_and_no_link(
    store: Store,
) -> None:
    reply = _begin(store)

    assert reply.skip is None
    assert reply.member is not None and reply.member.project_id == MEMBER_ID
    assert reply.answering is not None
    assert reply.answering.settings.answer_limit == CONFIG.answer_limit
    assert reply.answering_wait_seconds == CONFIG.answering_wait_seconds
    assert reply.resume_wait_seconds == CONFIG.resume_wait_seconds
    assert reply.row is None
    assert reply.limit is not None and not reply.limit.reached
    assert (reply.link_request_id, reply.link_problem) == (None, None)


def test_a_question_that_names_a_request_returns_the_link_or_why_not(
    store: Store,
) -> None:
    with store.write() as transaction:
        insert_request(
            transaction,
            message_id="request-a",
            from_member=MEMBER_ID,
            to_member="member-b",
            parent_id=None,
            parent_depth=None,
            subject="s",
            body="b",
            ttl=timedelta(days=1),
            now=NOW,
        )

    linked = _begin(store, question="Waiting. amoeba-request: request-a")
    bad = _begin(store, question="Waiting. amoeba-request: no-such-request")

    assert linked.link_request_id == "request-a"
    assert bad.link_problem is not None and "no-such-request" in bad.link_problem


def test_a_held_row_returns_its_requests_state_and_the_limit(store: Store) -> None:
    with store.write() as transaction:
        insert_request(
            transaction,
            message_id="request-a",
            from_member=MEMBER_ID,
            to_member="member-b",
            parent_id=None,
            parent_depth=None,
            subject="s",
            body="b",
            ttl=timedelta(days=1),
            now=NOW,
        )
        insert_held_row(transaction)

    reply = _begin(store)

    assert reply.row is not None
    assert reply.row.state is QuestionState.WAITING_ON_REQUEST
    assert reply.request is not None and reply.request.state is RequestState.OPEN
    assert reply.limit is not None and reply.limit.reached is False


def test_a_waiting_row_comes_back_with_no_limit_or_link(store: Store) -> None:
    with store.write() as transaction:
        insert_question(transaction, waiting_question(), now=NOW)

    reply = _begin(store)

    assert reply.row is not None
    assert reply.limit is None and reply.link_request_id is None


def test_claim_stale_is_false_one_second_under_the_limit_and_true_at_it(
    store: Store,
) -> None:
    with store.write() as transaction:
        insert_question(transaction, claimed_question(), now=NOW)
    limit = timedelta(seconds=pause_claim_seconds(CONFIG))

    young = _begin(store, at=limit - timedelta(seconds=1))
    old = _begin(store, at=limit)

    assert (young.claim_stale, old.claim_stale) == (False, True)


def test_the_sweep_closes_older_rows_on_this_machine_and_leaves_another_machines(
    store: Store,
) -> None:
    older = QuestionKey(KEY.run_id, "2026-11-01T08:00:00+00:00")
    other = QuestionKey(KEY.run_id, "2026-11-01T09:00:00+00:00")
    with store.write() as transaction:
        insert_question(transaction, waiting_question(older), now=NOW)
        insert_question(transaction, waiting_question(other), now=NOW)
        invite_machine(transaction, "beta", "a" * 64, NOW)
        beta = int(
            transaction.execute(
                "SELECT machine_id FROM machines WHERE name = 'beta'"
            ).fetchone()[0]
        )
        transaction.execute(
            "UPDATE questions SET machine_id = ? WHERE paused_at = ?",
            (beta, other.paused_at),
        )

    reply = _begin(
        store,
        fate=FateFields(
            reason=ClosedReason.RUN_MOVED_ON,
            detail=f"paused at {KEY.paused_at}",
            current_paused_at=KEY.paused_at,
        ),
    )

    assert [item.key for item in reply.swept.closed] == [older]
    with store.read() as transaction:
        mine = get_question(transaction, older)
        theirs = get_question(transaction, other)
    assert mine is not None and mine.state is QuestionState.CLOSED
    assert theirs is not None and theirs.state is QuestionState.WAITING_ON_PM
