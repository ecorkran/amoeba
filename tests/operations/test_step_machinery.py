"""``run_step`` and the step table (slice 262, D2, D3)."""

from __future__ import annotations

import types
import typing
from collections.abc import Iterator
from datetime import date, datetime, time, timedelta
from pathlib import Path

import pytest
from pydantic import BaseModel
from store.question_support import MEMBER_ID, NOW, seed_members
from store_open import open_local_store
from user_configs import user_config

from amoeba.config.user_config import UserConfig
from amoeba.operations.steps.dispatch import (
    STEP_FUNCTIONS,
    StepDocumentError,
    StepEdges,
    UnknownStepError,
    run_step,
)
from amoeba.operations.steps.models import (
    RESUME_CLAIM,
    RESUME_READ,
    RESUME_RECORD,
    STEP_MODELS,
    ClaimStatus,
    ResumeClaimReply,
    ResumeRecordReply,
)
from amoeba.store.answers import add_pm_answer, get_answer
from amoeba.store.models import AnswerRecord, QuestionKey
from amoeba.store.questions import NewQuestion, insert_question
from amoeba.store.store import Store
from amoeba.store.vocabulary import ResumeOutcome

TIME_TYPES = (datetime, date, time, timedelta)
KEY = QuestionKey("run-1", "2026-11-10T11:00:00+00:00")


def _types_in(annotation: object) -> Iterator[object]:
    """Every type an annotation mentions, through unions and generics."""
    yield annotation
    for argument in typing.get_args(annotation):
        yield from _types_in(argument)
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        for field in annotation.model_fields.values():
            yield from _types_in(field.annotation)
    if isinstance(annotation, types.UnionType):
        for member in annotation.__args__:
            yield from _types_in(member)


def test_every_step_has_a_function_and_the_table_is_keyed_by_name() -> None:
    assert set(STEP_FUNCTIONS) == set(STEP_MODELS)
    assert all(name == step.name for name, step in STEP_MODELS.items())


@pytest.mark.parametrize("name", sorted(STEP_MODELS))
def test_no_step_request_model_has_a_date_or_time_field(name: str) -> None:
    mentioned = list(_types_in(STEP_MODELS[name].request))

    assert not [kind for kind in mentioned if kind in TIME_TYPES]


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    with open_local_store(tmp_path / "amoeba.sqlite3") as opened:
        seed_members(opened)
        yield opened


def _answered(store: Store) -> int:
    new = NewQuestion(
        key=KEY,
        member_id=MEMBER_ID,
        question="q",
        checkout="/c",
        slice_label=None,
        source_commit=None,
        passages=None,
        answering_run_id="a-1",
        waiting_reason=None,
        waiting_detail=None,
    )
    with store.write() as transaction:
        insert_question(transaction, new, now=NOW)
        return add_pm_answer(transaction, KEY, "an answer", now=NOW, via=None)


def _edges(config: UserConfig | None = None) -> StepEdges:
    def load_config() -> UserConfig:
        if config is None:
            raise AssertionError("the step loaded a config it should not")
        return config

    return StepEdges(lambda: NOW, load_config)


def test_a_document_that_does_not_validate_is_refused_and_writes_nothing(
    store: Store,
) -> None:
    seq = _answered(store)

    with pytest.raises(StepDocumentError):
        run_step("resume_claim", store, {"answer_seq": seq, "extra": 1}, _edges())
    with pytest.raises(StepDocumentError):
        run_step("resume_claim", store, {"answer_seq": "not a number"}, _edges())

    with store.read() as transaction:
        answer = get_answer(transaction, seq)
    assert answer is not None
    assert answer.resume_claim_id is None


def test_an_unknown_step_is_refused(store: Store) -> None:
    with pytest.raises(UnknownStepError):
        run_step("no_such_step", store, {}, _edges())


def test_a_writing_step_commits_and_a_read_step_writes_nothing(store: Store) -> None:
    seq = _answered(store)
    config = user_config()

    claimed = run_step(RESUME_CLAIM.name, store, {"answer_seq": seq}, _edges(config))
    assert isinstance(claimed, ResumeClaimReply)
    assert claimed.status is ClaimStatus.CLAIMED
    assert claimed.claim is not None
    before = _answer_row(store, seq)

    run_step(
        RESUME_READ.name,
        store,
        {"answer_seq": seq, "claim_id": claimed.claim.claim_id},
        _edges(config),
    )

    assert before.resume_claim_id == claimed.claim.claim_id  # the write committed
    assert _answer_row(store, seq) == before  # the read changed nothing


def test_a_step_that_needs_no_config_loads_none(store: Store) -> None:
    seq = _answered(store)

    reply = run_step(
        RESUME_RECORD.name,
        store,
        {
            "answer_seq": seq,
            "claim_id": None,
            "outcome": ResumeOutcome.REFUSED.value,
            "detail": "why",
            "log": None,
        },
        _edges(None),
    )

    assert isinstance(reply, ResumeRecordReply)
    assert (reply.outcome, reply.detail, reply.wrote) == (
        ResumeOutcome.REFUSED,
        "why",
        True,
    )


def _answer_row(store: Store, seq: int) -> AnswerRecord:
    with store.read() as transaction:
        row = get_answer(transaction, seq)
    assert row is not None
    return row
