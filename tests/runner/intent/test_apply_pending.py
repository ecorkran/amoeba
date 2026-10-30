"""``apply_pending_intents``: order, outcomes, atomicity and the store's rules."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from fault_injection import InjectedFailureError, fail_on_statement

from amoeba.runner.faults import RUNNER_ACTOR
from amoeba.runner.intent import apply as apply_module
from amoeba.runner.intent.apply import Interpretation, apply_pending_intents
from amoeba.runner.intent.vocabulary import IntentRejection
from amoeba.store import (
    AcknowledgmentOutcome,
    Channel,
    DesiredState,
    Message,
    Node,
    Store,
    sql_runner,
)
from amoeba.store.runner_models import SetDesiredState
from runner.lifecycle.tree_support import PROJECT, TreeBuilder

from .intent_support import submit
from .merge_cases import CASES

APPLIED = AcknowledgmentOutcome.APPLIED


@pytest.fixture
def builder() -> Iterator[TreeBuilder]:
    tree_builder = TreeBuilder()
    yield tree_builder
    tree_builder.close()


def _message(store: Store, message_id: str) -> Message:
    found = [
        m for m in store.messages(PROJECT, channel=Channel.INTENT) if m.id == message_id
    ]
    assert len(found) == 1
    return found[0]


def test_no_pending_intents_returns_zero_without_reading_the_tree(
    builder: TreeBuilder, monkeypatch: pytest.MonkeyPatch
) -> None:
    reads: list[str] = []
    real = builder.store.nodes_for_project

    def spy(project_id: str) -> list[Node]:
        reads.append(project_id)
        return real(project_id)

    monkeypatch.setattr(builder.store, "nodes_for_project", spy)

    assert apply_pending_intents(builder.store, PROJECT) == 0
    assert reads == []


def test_each_outcome_is_stored_with_its_reason(builder: TreeBuilder) -> None:
    store = builder.store
    initiative = builder.initiative(140)
    orphan = builder.slice(initiative, 142)
    builder.orphan(orphan)
    step = builder.phase_node(initiative)
    applied = submit(store, {"intent": "drive"})
    no_op = submit(store, {"intent": "drive"})
    malformed = submit(store, {"intent": "launch"})
    not_target = submit(store, {"intent": "drive"}, node_id=step.id)
    unlinked = submit(store, {"intent": "drive"}, node_id=orphan.id)
    with_until = submit(store, {"intent": "drive", "until": "tasks"}, node_id=None)

    assert apply_pending_intents(store, PROJECT) == 6

    expected = {
        applied: (APPLIED, None),
        no_op: (AcknowledgmentOutcome.NO_OP, None),
    }
    for message_id, (outcome, reason) in expected.items():
        message = _message(store, message_id)
        assert (message.acknowledgment_outcome, message.acknowledgment_reason) == (
            outcome,
            reason,
        )
        assert message.acknowledged_by == RUNNER_ACTOR
    rejected = {
        malformed: IntentRejection.MALFORMED_BODY,
        not_target: IntentRejection.TARGET_NOT_INITIATIVE_OR_SLICE,
        unlinked: IntentRejection.TARGET_UNLINKED,
        with_until: IntentRejection.MALFORMED_BODY,
    }
    for message_id, code in rejected.items():
        message = _message(store, message_id)
        assert message.acknowledgment_outcome is AcknowledgmentOutcome.REJECTED
        assert (message.acknowledgment_reason or "").startswith(f"{code.value}: ")
    assert store.pending_intents(PROJECT) == []


def test_intents_for_one_target_apply_in_seq_order(builder: TreeBuilder) -> None:
    store = builder.store
    submit(store, {"intent": "exclude"})
    submit(store, {"intent": "drive"})

    apply_pending_intents(store, PROJECT)

    row = store.desired_state(PROJECT)
    assert row is not None
    assert row.drive is True and row.drive_until_step is None


def test_the_row_names_the_intent_that_last_changed_it(builder: TreeBuilder) -> None:
    store = builder.store
    first = submit(store, {"intent": "drive"})
    apply_pending_intents(store, PROJECT)
    submit(store, {"intent": "drive"})  # no-op
    apply_pending_intents(store, PROJECT)
    row = store.desired_state(PROJECT)
    assert row is not None and row.message_id == first

    third = submit(store, {"intent": "pause"})
    apply_pending_intents(store, PROJECT)
    row = store.desired_state(PROJECT)
    assert row is not None and row.message_id == third


def test_an_intent_is_applied_without_any_cf_link(builder: TreeBuilder) -> None:
    assert builder.store.cf_links(PROJECT) == []
    message_id = submit(builder.store, {"intent": "pause"})
    assert apply_pending_intents(builder.store, PROJECT) == 1
    assert _message(builder.store, message_id).acknowledgment_outcome is APPLIED


def test_a_crash_inside_the_acknowledgment_leaves_the_intent_pending(
    builder: TreeBuilder, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = builder.store
    message_id = submit(store, {"intent": "drive"})
    with monkeypatch.context() as patch:
        fail_on_statement(patch, store, sql_runner.INSERT_DESIRED_STATE)
        with pytest.raises(InjectedFailureError):
            apply_pending_intents(store, PROJECT)

    assert [m.id for m in store.pending_intents(PROJECT)] == [message_id]
    assert store.desired_states(PROJECT) == []

    assert apply_pending_intents(store, PROJECT) == 1
    assert len(store.desired_states(PROJECT)) == 1
    assert apply_pending_intents(store, PROJECT) == 0


def _seed_bodies(fields: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Intents that build the row ``fields`` describes."""
    bodies: list[dict[str, Any]] = []
    if fields is None:
        return bodies
    if fields.get("drive") is False:
        bodies.append({"intent": "exclude"})
    if fields.get("drive") is True:
        bodies.append({"intent": "drive"})
    if fields.get("hold"):
        bodies.append({"intent": "pause"})
    return bodies


def _fields(row: DesiredState | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        key: value
        for key, value in {
            "drive": row.drive,
            "drive_until_step": row.drive_until_step,
            "hold": row.hold,
        }.items()
        if value is not None
    }


@pytest.mark.parametrize(
    ("row", "body", "change"),
    [case[1:3] + case[4:] for case in CASES if case[3] is APPLIED],
    ids=[case[0] for case in CASES if case[3] is APPLIED],
)
def test_every_applied_merge_is_accepted_by_the_store(
    builder: TreeBuilder,
    row: dict[str, Any] | None,
    body: dict[str, Any],
    change: object,
) -> None:
    store = builder.store
    for seed in _seed_bodies(row):
        submit(store, seed)
    apply_pending_intents(store, PROJECT)
    assert _fields(store.desired_state(PROJECT)) == row

    message_id = submit(store, body)
    apply_pending_intents(store, PROJECT)

    assert _message(store, message_id).acknowledgment_outcome is APPLIED
    expected = (
        None
        if not isinstance(change, SetDesiredState)
        else {
            key: value
            for key, value in {
                "drive": change.drive,
                "drive_until_step": change.drive_until_step,
                "hold": change.hold,
            }.items()
            if value is not None
        }
    )
    assert _fields(store.desired_state(PROJECT)) == expected


def test_a_change_that_breaks_the_shape_rules_raises_and_stays_pending(
    builder: TreeBuilder, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = builder.store
    message_id = submit(store, {"intent": "drive"})

    def sets_nothing(*_: object) -> Interpretation:
        # A set with no drive and no hold breaks 121's shape rules.
        return Interpretation(APPLIED, desired_state=SetDesiredState())

    monkeypatch.setattr(apply_module, "interpret", sets_nothing)

    with pytest.raises(ValueError):
        apply_pending_intents(store, PROJECT)

    assert [m.id for m in store.pending_intents(PROJECT)] == [message_id]
