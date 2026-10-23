"""D3's escalation-on-block invariant and the message read API.

Intent rows are staged with the store's own ``INSERT_MESSAGE`` statement,
because the only production writer of intents is ``apply_submission``, which
this test module must not depend on.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sq_run_fixtures import sq_run_parameters

from amoeba.store import AcknowledgmentOutcome, SubmissionKind, sql_inbox
from amoeba.store.inbox_models import Channel
from amoeba.store.journal_models import CommandKind
from amoeba.store.models import BlockedKind, InvalidTransitionError, NodeKind
from amoeba.store.store import Store

PROJECT = "demo"
APPLIED = AcknowledgmentOutcome.APPLIED
STAGED_AT = "2026-09-23T00:00:00+00:00"


def _make_node(store: Store, title: str = "a slice") -> str:
    return store.create_node(project_id=PROJECT, kind=NodeKind.SLICE, title=title).id


def _escalations(store: Store, after_seq: int = 0) -> list[str]:
    """Blocked-state ids carried by escalation rows, in seq order."""
    return [
        str(message.blocked_state_id)
        for message in store.messages(
            PROJECT, channel=Channel.ESCALATION, after_seq=after_seq
        )
    ]


def _stage_intent(path: Path, message_id: str) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute(
            sql_inbox.INSERT_MESSAGE,
            (
                message_id,
                PROJECT,
                Channel.INTENT.value,
                None,
                None,
                None,
                f"sub-{message_id}",
                json.dumps({"want": message_id}),
                STAGED_AT,
            ),
        )


# --------------------------------------------------------------------------
# D3: the escalation row
# --------------------------------------------------------------------------


def test_human_block_writes_exactly_one_escalation(store_file: Path) -> None:
    with Store.open(store_file) as store:
        node_id = _make_node(store)
        blocked = store.block(node_id, kind=BlockedKind.HUMAN, context="decide")

        escalations = store.messages(PROJECT, channel=Channel.ESCALATION)

    assert len(escalations) == 1
    assert escalations[0].node_id == node_id
    assert escalations[0].blocked_state_id == blocked.id
    assert escalations[0].project_id == PROJECT
    assert escalations[0].journal_entry_id is None


@pytest.mark.parametrize("kind", [BlockedKind.JUDGE, BlockedKind.SQ_CHECKPOINT])
def test_non_human_blocks_write_no_message(store_file: Path, kind: BlockedKind) -> None:
    with Store.open(store_file) as store:
        store.block(_make_node(store), kind=kind, context="machine-resolved")

        assert store.messages(PROJECT, channel=Channel.ESCALATION) == []
        assert store.messages(PROJECT, channel=Channel.INTENT) == []


def test_block_payload_round_trips_onto_the_escalation(store_file: Path) -> None:
    payload = {"options": ["ship", "hold"], "deadline": "friday"}

    with Store.open(store_file) as store:
        store.block(
            _make_node(store), kind=BlockedKind.HUMAN, context="c", payload=payload
        )
        [escalation] = store.messages(PROJECT, channel=Channel.ESCALATION)

    assert escalation.payload == payload


def test_omitted_payload_is_stored_as_null(store_file: Path) -> None:
    with Store.open(store_file) as store:
        store.block(_make_node(store), kind=BlockedKind.HUMAN, context="c")
        [escalation] = store.messages(PROJECT, channel=Channel.ESCALATION)

    assert escalation.payload is None


def test_a_failed_block_writes_no_escalation(store_file: Path) -> None:
    """The row commits with the block or neither does."""
    with Store.open(store_file) as store:
        node_id = _make_node(store)
        store.block(node_id, kind=BlockedKind.HUMAN, context="first")

        with pytest.raises(InvalidTransitionError):
            store.block(node_id, kind=BlockedKind.HUMAN, context="second")

        assert len(store.messages(PROJECT, channel=Channel.ESCALATION)) == 1


# --------------------------------------------------------------------------
# The replay primitive
# --------------------------------------------------------------------------


def test_messages_after_seq_returns_only_later_rows_in_order(
    store_file: Path,
) -> None:
    with Store.open(store_file) as store:
        first = store.block(
            _make_node(store, "one"), kind=BlockedKind.HUMAN, context="1"
        )
        second = store.block(
            _make_node(store, "two"), kind=BlockedKind.HUMAN, context="2"
        )
        third = store.block(
            _make_node(store, "three"), kind=BlockedKind.HUMAN, context="3"
        )
        all_rows = store.messages(PROJECT, channel=Channel.ESCALATION)

    assert [row.blocked_state_id for row in all_rows] == [first.id, second.id, third.id]
    assert [row.seq for row in all_rows] == sorted(row.seq for row in all_rows)

    with Store.open_read_only(store_file) as reader:
        after_first = _escalations(reader, after_seq=all_rows[0].seq)
        again = _escalations(reader, after_seq=all_rows[0].seq)

    assert after_first == [second.id, third.id]
    assert again == after_first


def test_messages_are_scoped_to_one_channel(store_file: Path) -> None:
    with Store.open(store_file) as store:
        store.block(_make_node(store), kind=BlockedKind.HUMAN, context="c")
    _stage_intent(store_file, "i-1")

    with Store.open_read_only(store_file) as reader:
        assert [m.id for m in reader.messages(PROJECT, channel=Channel.INTENT)] == [
            "i-1"
        ]
        assert len(reader.messages(PROJECT, channel=Channel.ESCALATION)) == 1


# --------------------------------------------------------------------------
# The intent queue
# --------------------------------------------------------------------------


def test_pending_intents_excludes_acknowledged_rows(store_file: Path) -> None:
    with Store.open(store_file):
        pass
    _stage_intent(store_file, "i-1")
    _stage_intent(store_file, "i-2")

    with Store.open(store_file) as store:
        acknowledged = store.acknowledge_message(
            "i-1", acknowledged_by="runner", outcome=APPLIED
        )
        pending = store.pending_intents(PROJECT)

    assert acknowledged.is_acknowledged
    assert acknowledged.acknowledged_by == "runner"
    assert [message.id for message in pending] == ["i-2"]


def test_second_acknowledge_raises(store_file: Path) -> None:
    with Store.open(store_file):
        pass
    _stage_intent(store_file, "i-1")

    with Store.open(store_file) as store:
        store.acknowledge_message("i-1", acknowledged_by="runner", outcome=APPLIED)

        with pytest.raises(InvalidTransitionError):
            store.acknowledge_message(
                "i-1", acknowledged_by="someone-else", outcome=APPLIED
            )

        [row] = store.messages(PROJECT, channel=Channel.INTENT)
        assert row.acknowledged_by == "runner"


def test_acknowledging_an_escalation_raises(store_file: Path) -> None:
    with Store.open(store_file) as store:
        store.block(_make_node(store), kind=BlockedKind.HUMAN, context="c")
        [escalation] = store.messages(PROJECT, channel=Channel.ESCALATION)

        with pytest.raises(InvalidTransitionError):
            store.acknowledge_message(
                escalation.id, acknowledged_by="runner", outcome=APPLIED
            )


def test_acknowledging_an_unknown_message_raises(store_file: Path) -> None:
    with Store.open(store_file) as store:
        with pytest.raises(InvalidTransitionError):
            store.acknowledge_message(
                "no-such-message", acknowledged_by="runner", outcome=APPLIED
            )


# --------------------------------------------------------------------------
# D2: acknowledgment outcomes
# --------------------------------------------------------------------------


@pytest.mark.parametrize("outcome", list(AcknowledgmentOutcome))
def test_each_outcome_round_trips(
    store_file: Path, outcome: AcknowledgmentOutcome
) -> None:
    with Store.open(store_file):
        pass
    _stage_intent(store_file, "i-1")

    with Store.open(store_file) as store:
        returned = store.acknowledge_message(
            "i-1", acknowledged_by="runner", outcome=outcome, reason="because"
        )
        [stored] = store.messages(PROJECT, channel=Channel.INTENT)

    assert returned == stored
    assert stored.acknowledgment_outcome is outcome
    assert stored.acknowledgment_reason == "because"


@pytest.mark.parametrize(
    "outcome", [AcknowledgmentOutcome.APPLIED, AcknowledgmentOutcome.NO_OP]
)
def test_applied_and_no_op_need_no_reason(
    store_file: Path, outcome: AcknowledgmentOutcome
) -> None:
    with Store.open(store_file):
        pass
    _stage_intent(store_file, "i-1")

    with Store.open(store_file) as store:
        message = store.acknowledge_message("i-1", acknowledged_by="r", outcome=outcome)

    assert message.acknowledgment_reason is None


@pytest.mark.parametrize("reason", [None, "", "   "])
def test_rejected_without_a_usable_reason_raises_and_writes_nothing(
    store_file: Path, reason: str | None
) -> None:
    with Store.open(store_file):
        pass
    _stage_intent(store_file, "i-1")

    with Store.open(store_file) as store:
        with pytest.raises(ValueError, match="reason"):
            store.acknowledge_message(
                "i-1",
                acknowledged_by="r",
                outcome=AcknowledgmentOutcome.REJECTED,
                reason=reason,
            )
        assert [m.id for m in store.pending_intents(PROJECT)] == ["i-1"]


def test_an_empty_reason_is_refused_for_any_outcome(store_file: Path) -> None:
    with Store.open(store_file):
        pass
    _stage_intent(store_file, "i-1")

    with Store.open(store_file) as store:
        with pytest.raises(ValueError, match="reason"):
            store.acknowledge_message(
                "i-1", acknowledged_by="r", outcome=APPLIED, reason=""
            )
        assert [m.id for m in store.pending_intents(PROJECT)] == ["i-1"]


def test_an_unknown_outcome_raises_and_writes_nothing(store_file: Path) -> None:
    with Store.open(store_file):
        pass
    _stage_intent(store_file, "i-1")

    with Store.open(store_file) as store:
        with pytest.raises(ValueError):
            store.acknowledge_message(
                "i-1",
                acknowledged_by="r",
                outcome="maybe",  # pyright: ignore[reportArgumentType]
            )
        assert [m.id for m in store.pending_intents(PROJECT)] == ["i-1"]


def test_outcome_is_required(store_file: Path) -> None:
    with Store.open(store_file):
        pass
    _stage_intent(store_file, "i-1")

    with Store.open(store_file) as store:
        with pytest.raises(TypeError):
            store.acknowledge_message("i-1", acknowledged_by="r")  # pyright: ignore[reportCallIssue]


def test_second_acknowledgment_keeps_the_first_outcome(store_file: Path) -> None:
    with Store.open(store_file):
        pass
    _stage_intent(store_file, "i-1")

    with Store.open(store_file) as store:
        store.acknowledge_message(
            "i-1", acknowledged_by="a", outcome=AcknowledgmentOutcome.NO_OP
        )
        with pytest.raises(InvalidTransitionError):
            store.acknowledge_message("i-1", acknowledged_by="b", outcome=APPLIED)
        [row] = store.messages(PROJECT, channel=Channel.INTENT)

    assert row.acknowledgment_outcome is AcknowledgmentOutcome.NO_OP


def test_a_row_acknowledged_before_outcomes_reads_back_with_none(
    store_file: Path,
) -> None:
    with Store.open(store_file):
        pass
    _stage_intent(store_file, "i-1")
    with sqlite3.connect(store_file) as connection:
        connection.execute(
            "UPDATE messages SET acknowledged_at = ?, acknowledged_by = ? WHERE id = ?",
            (STAGED_AT, "old-runner", "i-1"),
        )

    with Store.open(store_file) as store:
        [row] = store.messages(PROJECT, channel=Channel.INTENT)

    assert row.is_acknowledged
    assert row.acknowledgment_outcome is None


def _submit_intent(store: Store, submission_id: str) -> None:
    store.apply_submission(
        submission_id=submission_id,
        project_id=PROJECT,
        kind=SubmissionKind.INTENT,
        submitted_by="pm",
        submitted_at=datetime(2026, 10, 22, tzinfo=UTC),
        payload={"node_id": None, "body": {"hold": True}},
    )


def test_intent_for_submission_before_and_after_acknowledgment(
    store_file: Path,
) -> None:
    with Store.open(store_file) as store:
        _submit_intent(store, "sub-1")
        before = store.intent_for_submission("sub-1")
        assert before is not None and not before.is_acknowledged
        store.acknowledge_message(
            before.id,
            acknowledged_by="runner",
            outcome=AcknowledgmentOutcome.NO_OP,
            reason="already held",
        )
        after = store.intent_for_submission("sub-1")

    assert after is not None
    assert after.id == before.id
    assert after.acknowledgment_outcome is AcknowledgmentOutcome.NO_OP
    assert store_file.exists()
    with Store.open_read_only(store_file) as reader:
        assert reader.intent_for_submission("sub-1") == after


def test_intent_for_an_unknown_submission_is_none(store: Store) -> None:
    assert store.intent_for_submission("never-submitted") is None


# --------------------------------------------------------------------------
# D3 on recovery's path: journal_escalate
# --------------------------------------------------------------------------


def _issue(store: Store, node_id: str) -> str:
    return store.journal_issue(
        node_id,
        kind=CommandKind.SQ_RUN,
        parameters=sq_run_parameters({"pipeline": "review", "params": {}}),
    ).id


def test_escalating_an_unblocked_node_escalates_with_the_entry(
    store_file: Path,
) -> None:
    with Store.open(store_file) as store:
        node_id = _make_node(store)
        entry_id = _issue(store, node_id)

        store.journal_escalate(entry_id, reason="lost track")

        block = store.blocked_state_for(node_id)
        [escalation] = store.messages(PROJECT, channel=Channel.ESCALATION)

    assert block is not None
    assert block.kind is BlockedKind.HUMAN
    assert escalation.blocked_state_id == block.id
    assert escalation.journal_entry_id == entry_id


@pytest.mark.parametrize("existing_kind", [BlockedKind.HUMAN, BlockedKind.JUDGE])
def test_escalating_an_already_blocked_node_points_at_the_existing_block(
    store_file: Path, existing_kind: BlockedKind
) -> None:
    """No second block; one new escalation, against the block already there."""
    with Store.open(store_file) as store:
        node_id = _make_node(store)
        entry_id = _issue(store, node_id)
        existing = store.block(node_id, kind=existing_kind, context="already")
        before = store.messages(PROJECT, channel=Channel.ESCALATION)

        store.journal_escalate(entry_id, reason="lost track")

        after = store.messages(PROJECT, channel=Channel.ESCALATION)
        blocks = list(store.all_blocked_states(node_id))

    assert [block.id for block in blocks] == [existing.id]

    [raised] = after[len(before) :]
    assert raised.blocked_state_id == existing.id
    assert raised.journal_entry_id == entry_id
    assert raised.node_id == node_id
