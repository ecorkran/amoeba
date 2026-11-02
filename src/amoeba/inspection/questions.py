"""Rows for the ``questions`` listing (slice 141, D8).

Both ``--json`` and the server add ``blocked_state_id``, ``source_entry_id`` and
``updated_at`` to the table's columns. The listing receives a **read-only** store.
"""

from __future__ import annotations

from typing import Final

from amoeba.inspection.listing import NODE_OPTION, ChoiceOption, ListingRequest, Row
from amoeba.store import QuestionRecord, QuestionState, Store

QUESTION_COLUMNS: Final = (
    "id",
    "node_id",
    "run_id",
    "step",
    "state",
    "answered_by",
    "question",
    "outcome",
    "truncated",
    "created_at",
)

STATE_OPTION = ChoiceOption(
    name="state",
    help_text="Only this state. Every state when omitted.",
    choices=tuple(state.value for state in QuestionState),
)


def _outcome(record: QuestionRecord) -> str:
    """The answer when answered, the decline reason when declined, else empty."""
    if record.state is QuestionState.ANSWERED:
        return record.answer or ""
    if record.state is QuestionState.DECLINED and record.decline_reason is not None:
        return record.decline_reason.value
    return ""


def question_rows(store: Store, request: ListingRequest) -> list[Row]:
    """A project's question records, oldest first, optionally by state and node."""
    chosen = request.option(STATE_OPTION)
    return [
        {
            "id": record.id,
            "node_id": record.node_id,
            "run_id": record.run_id,
            "step": record.step or "",
            "state": record.state.value,
            "answered_by": record.answered_by.value if record.answered_by else "",
            "question": record.question or "",
            "outcome": _outcome(record),
            "truncated": record.truncated,
            "created_at": record.created_at.isoformat(),
            "blocked_state_id": record.blocked_state_id,
            "source_entry_id": record.source_entry_id,
            "updated_at": record.updated_at.isoformat(),
        }
        for record in store.questions(
            request.require_project_id(),
            state=None if chosen is None else QuestionState(chosen),
            node_id=request.option(NODE_OPTION),
        )
    ]
