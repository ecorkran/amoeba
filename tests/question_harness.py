"""Test rig for question records: seed a row directly, in any state.

Rows are inserted through the store's own SQL constants, not ``record_question``,
so tests of the reads and of the writers can stage any state they need.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sq_run_fixtures import sq_run_parameters

from amoeba.store import (
    AnsweredBy,
    DeclineReason,
    NodeKind,
    QuestionCatch,
    QuestionRecord,
    QuestionState,
    Store,
)
from amoeba.store import sql_questions as sql_q
from amoeba.store._base import isoformat, new_id, now
from amoeba.store.inbox_models import (
    RESOLUTION_BLOCKED_STATE_ID,
    RESOLUTION_DECISION,
    RESOLUTION_DETAIL,
    RESOLUTION_INSTRUCTIONS,
    SubmissionKind,
)
from amoeba.store.journal_models import CommandKind

PROJECT = "demo"
SUBMITTED_AT = datetime(2026, 11, 2, 12, 0, tzinfo=UTC)


def make_slice(store: Store, project_id: str = PROJECT) -> str:
    """A slice node, and its id."""
    return store.create_node(
        project_id=project_id, kind=NodeKind.SLICE, title="slice"
    ).id


def issue_entry(store: Store, node_id: str) -> str:
    """Journal an ``sq_run`` on the node, and return the entry id."""
    return store.journal_issue(
        node_id,
        kind=CommandKind.SQ_RUN,
        parameters=sq_run_parameters({"pipeline": "p6", "params": {}}),
    ).id


def catch_for(
    store: Store,
    node_id: str,
    *,
    question: str | None = "which branch?",
    truncated: bool = False,
) -> QuestionCatch:
    """A catch on a fresh journal entry of the node."""
    return QuestionCatch(
        project_id=PROJECT,
        node_id=node_id,
        source_entry_id=issue_entry(store, node_id),
        run_id="run-test",
        step="implement",
        question=question,
        truncated=truncated,
    )


def seed_question(
    store: Store,
    node_id: str,
    *,
    state: QuestionState = QuestionState.PENDING,
    project_id: str = PROJECT,
    blocked_state_id: str | None = None,
    question: str | None = "which branch?",
    answered_by: AnsweredBy | None = None,
    answer: str | None = None,
    decline_reason: DeclineReason | None = None,
    truncated: bool = False,
    reserved_term: str | None = None,
) -> QuestionRecord:
    """Insert one record, with a journal entry of its own for the unique key."""
    entry = store.journal_issue(
        node_id,
        kind=CommandKind.SQ_RUN,
        parameters=sq_run_parameters({"pipeline": "p6", "params": {}}),
    )
    stamp = isoformat(now())
    values: dict[str, object] = {
        sql_q.COL_QUESTION_ID: new_id(),
        sql_q.COL_QUESTION_PROJECT_ID: project_id,
        sql_q.COL_QUESTION_NODE_ID: node_id,
        sql_q.COL_QUESTION_SOURCE_ENTRY_ID: entry.id,
        sql_q.COL_QUESTION_RUN_ID: "run-test",
        sql_q.COL_QUESTION_STEP: "implement",
        sql_q.COL_QUESTION_TEXT: question,
        sql_q.COL_QUESTION_TRUNCATED: 1 if truncated else 0,
        sql_q.COL_QUESTION_BLOCKED_STATE_ID: blocked_state_id,
        sql_q.COL_QUESTION_STATE: state.value,
        sql_q.COL_QUESTION_ANSWERED_BY: None
        if answered_by is None
        else answered_by.value,
        sql_q.COL_QUESTION_ANSWER: answer,
        sql_q.COL_QUESTION_DECLINE_REASON: (
            None if decline_reason is None else decline_reason.value
        ),
        sql_q.COL_QUESTION_CREATED_AT: stamp,
        sql_q.COL_QUESTION_UPDATED_AT: stamp,
        sql_q.COL_QUESTION_RESERVED_TERM: reserved_term,
    }
    with store._connection:  # pyright: ignore[reportPrivateUsage]
        store._connection.execute(  # pyright: ignore[reportPrivateUsage]
            sql_q.INSERT_QUESTION,
            tuple(values[column] for column in sql_q.QUESTION_COLUMNS),
        )
    stored = store.question(str(values[sql_q.COL_QUESTION_ID]))
    assert stored is not None
    return stored


def submit_resolution(
    store: Store,
    blocked_state_id: str,
    decision: str,
    *,
    instructions: str | None = None,
    submitted_by: str = "pm",
) -> None:
    payload: dict[str, object] = {
        RESOLUTION_BLOCKED_STATE_ID: blocked_state_id,
        RESOLUTION_DETAIL: "answered",
        RESOLUTION_DECISION: decision,
    }
    if instructions is not None:
        payload[RESOLUTION_INSTRUCTIONS] = instructions
    store.apply_submission(
        submission_id=f"s-{blocked_state_id}",
        project_id=PROJECT,
        kind=SubmissionKind.RESOLUTION,
        submitted_by=submitted_by,
        submitted_at=SUBMITTED_AT,
        payload=payload,
    )
