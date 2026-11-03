"""Rows for the ``questions`` listing (slice 141, D8).

Both ``--json`` and the server add ``blocked_state_id``, ``source_entry_id`` and
``updated_at`` to the table's columns, and (slice 144) every answering-run column:
``answering_entry_id``, ``source_commit``, ``passage_index`` (id, source, question
id and date of each passage, never its text), ``dropped_pm_answers``,
``proposed_answer``, ``cited_passages`` and ``check_reason``. The table shows the
answering run's id, the check's verdict and the decline detail. The listing
receives a **read-only** store.
"""

from __future__ import annotations

from typing import Final

from amoeba.inspection.listing import NODE_OPTION, ChoiceOption, ListingRequest, Row
from amoeba.store import PARAM_RUN_ID, QuestionRecord, QuestionState, Store

QUESTION_COLUMNS: Final = (
    "id",
    "node_id",
    "run_id",
    "step",
    "state",
    "answered_by",
    "question",
    "outcome",
    "reserved_term",
    "truncated",
    "created_at",
    "answering_run_id",
    "check_verdict",
    "decline_detail",
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


def _answering_run_id(store: Store, record: QuestionRecord) -> str:
    """The run id of the record's answering entry; empty when it had none."""
    if record.answering_entry_id is None:
        return ""
    entry = store.journal_entry(record.answering_entry_id)
    return "" if entry is None else str(entry.parameters.get(PARAM_RUN_ID, ""))


def _passage_index(record: QuestionRecord) -> list[dict[str, object]] | None:
    if record.passage_index is None:
        return None
    return [
        {
            "id": passage.id,
            "source": passage.source,
            "question_id": passage.question_id,
            "date": passage.date.isoformat(),
        }
        for passage in record.passage_index
    ]


def _list_or_none(values: tuple[str, ...] | None) -> list[str] | None:
    return None if values is None else list(values)


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
            "reserved_term": record.reserved_term or "",
            "truncated": record.truncated,
            "created_at": record.created_at.isoformat(),
            "answering_run_id": _answering_run_id(store, record),
            "check_verdict": record.check_verdict or "",
            "decline_detail": record.decline_detail or "",
            "blocked_state_id": record.blocked_state_id,
            "source_entry_id": record.source_entry_id,
            "updated_at": record.updated_at.isoformat(),
            "answering_entry_id": record.answering_entry_id,
            "source_commit": record.source_commit,
            "passage_index": _passage_index(record),
            "dropped_pm_answers": _list_or_none(record.dropped_pm_answers),
            "proposed_answer": record.proposed_answer,
            "cited_passages": _list_or_none(record.cited_passages),
            "check_reason": record.check_reason,
        }
        for record in store.questions(
            request.require_project_id(),
            state=None if chosen is None else QuestionState(chosen),
            node_id=request.option(NODE_OPTION),
        )
    ]
