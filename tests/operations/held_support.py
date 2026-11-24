"""Held questions and their requests in a ``handle_rig`` world (slice 242)."""

from __future__ import annotations

from datetime import datetime, timedelta

from amoeba.answering.values import AnsweringEvidence
from amoeba.operations.here_document import HereCaller
from amoeba.operations.pause_results import PauseTarget
from amoeba.operations.steps.dispatch import StepEdges
from amoeba.operations.steps.models import PAUSE_BEGIN
from amoeba.operations.steps.models_pause import PauseBeginReply, PauseBeginRequest
from amoeba.operations.store_steps import LocalSteps
from amoeba.store.answers import Settled, record_resume, settle_answered
from amoeba.store.held_questions import HeldQuestion, insert_held
from amoeba.store.message_transitions import StateFields, change_state
from amoeba.store.messages import get_message, insert_request
from amoeba.store.models import Message, QuestionKey
from amoeba.store.questions import NewQuestion, insert_question
from amoeba.store.store import Store
from amoeba.store.vocabulary import DeliveryEvent, RequestState, ResumeOutcome
from amoeba.upstream.squadron.run_file import RunFacts, read_run_facts
from amoeba.wiring_steps import LastReply, after_call
from operations.handle_rig import KEY, PROJECT_ID, QUESTION, RUN, World
from operations.pause_support import START, register_member

#: The member the asking member sends its requests to.
ADDRESSEE = "addressee-project"
REQUEST_ID = "guide-change"
RESULT = "The guide now says source files stay near 300 lines."
RESULT_COMMIT = "abc1234"
RESULT_VERSION = "v1.4"
#: Long enough that a test's clock never reaches it unless it means to.
TTL = timedelta(days=30)
#: The delivery event each end state writes.
_EVENTS = {
    RequestState.ACCEPTED: DeliveryEvent.ACCEPTED,
    RequestState.DONE: DeliveryEvent.DONE,
    RequestState.DECLINED: DeliveryEvent.DECLINED,
    RequestState.CANCELLED: DeliveryEvent.CANCELLED,
    RequestState.EXPIRED: DeliveryEvent.EXPIRED,
}


def add_addressee(store: Store) -> None:
    register_member(store, ADDRESSEE)


def seed_request(  # noqa: PLR0913 - the request's fields a test chooses
    store: Store,
    state: RequestState,
    *,
    request_id: str = REQUEST_ID,
    from_member: str = PROJECT_ID,
    to_member: str = ADDRESSEE,
    reason: str | None = None,
    now: datetime = START,
    ttl: timedelta = TTL,
) -> Message:
    """A request from ``from_member`` moved to ``state``; ``done`` carries the
    result, commit and version above."""
    with store.write() as transaction:
        message = insert_request(
            transaction,
            message_id=request_id,
            from_member=from_member,
            to_member=to_member,
            parent_id=None,
            parent_depth=None,
            subject="Add the length rule",
            body="Please add the length rule to the guide.",
            ttl=ttl,
            now=now,
        )
        if state is RequestState.OPEN:
            return message
        done = state is RequestState.DONE
        fields = StateFields(
            result=RESULT if done else None,
            result_commit=RESULT_COMMIT if done else None,
            result_version=RESULT_VERSION if done else None,
            reason=reason,
            accepted_at=now if state is RequestState.ACCEPTED else None,
        )
        return change_state(
            transaction, message, state, _EVENTS[state], to_member, now, fields
        )


def end_request(
    store: Store, state: RequestState, *, request_id: str = REQUEST_ID, now: datetime
) -> None:
    """Move an existing request to ``state`` as its addressee would."""
    with store.write() as transaction:
        message = get_message(transaction, request_id)
        assert message is not None
        done = state is RequestState.DONE
        fields = StateFields(
            result=RESULT if done else None,
            result_commit=RESULT_COMMIT if done else None,
            result_version=RESULT_VERSION if done else None,
        )
        change_state(
            transaction, message, state, _EVENTS[state], message.to_member, now, fields
        )


def hold(w: World, *, request_id: str = REQUEST_ID, now: datetime = START) -> None:
    """The paused question, held on ``request_id``."""
    held = HeldQuestion(KEY, PROJECT_ID, QUESTION, str(w.directory))
    with w.store.write() as transaction:
        assert insert_held(transaction, held, request_id, now)


def target_of(w: World) -> PauseTarget:
    facts = read_run_facts(w.runs_dir, RUN)
    assert isinstance(facts, RunFacts)
    return PauseTarget(KEY, QUESTION, w.directory, w.member, PROJECT_ID, facts)


def steps_for(w: World) -> LocalSteps:
    """The world's local steps, on its store, config and clock."""
    return LocalSteps(w.store, StepEdges(w.deps.clock, lambda: w.config))


def run_after_step(w: World) -> None:
    """The after-step with the flag read locally, as the CLI makes it after any call."""
    after_call(steps_for(w), lambda: w.deps, LastReply(), prunes=False)


def begin_for(w: World) -> PauseBeginReply:
    """What ``pause_begin`` tells ``handle_pause`` about the paused question now."""
    return steps_for(w).run(
        PAUSE_BEGIN,
        PauseBeginRequest(
            run_id=KEY.run_id,
            here=HereCaller(project_id=PROJECT_ID),
            outcome="paused",
            paused=True,
            checkpoint_kind="agent_question",
            paused_at=KEY.paused_at,
            question=QUESTION,
            fate=None,
        ),
    )


def automatic_answers_to_the_limit(w: World) -> None:
    for number in range(w.config.answer_limit):
        earlier = QuestionKey(KEY.run_id, f"2026-11-09T0{number}:00:00+00:00")
        new = NewQuestion(
            key=earlier, member_id=PROJECT_ID, question="q", checkout="/c",
            slice_label=None, source_commit=None, passages=None,
            answering_run_id=f"earlier-{number}", waiting_reason=None,
            waiting_detail=None,
        )  # fmt: skip
        with w.store.write() as transaction:
            insert_question(transaction, new, now=START)
        settled = settle_answered(
            w.store, earlier, f"earlier-{number}", answer="x", cited=(),
            evidence=AnsweringEvidence(), gate=lambda _prior: None, now=START,
        )  # fmt: skip
        assert isinstance(settled, Settled)
        # Settled and handed over long ago: nothing of it is left for the after-step.
        with w.store.write() as transaction:
            record_resume(
                transaction, settled.answer_seq, ResumeOutcome.RESUMED,
                detail=None, log=None, at=START, claim_id=None,
            )  # fmt: skip
