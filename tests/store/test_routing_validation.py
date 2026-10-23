"""D5: the checks a routing decision passes, through the public method."""

from __future__ import annotations

import pytest
from routing_helpers import PROJECT, TABLE
from routing_helpers import decision_input as _decision

from amoeba.store import (
    REQUIRED_PARAMETER_KEYS,
    BlockEffect,
    CommandKind,
    InvalidTransitionError,
    JournalOutcome,
    NodeKind,
    NodeNotFoundError,
    NodeStatus,
    RoutingDecisionInput,
    RoutingTableVersion,
    StatusEffect,
    Store,
)


def _check(
    store: Store,
    decision: RoutingDecisionInput,
    *,
    table: RoutingTableVersion = TABLE,
    effect: StatusEffect | BlockEffect | None = None,
    attempt_step: str | None = None,
) -> None:
    store.record_routing_decision(
        decision, table=table, effect=effect, attempt_step=attempt_step
    )


@pytest.fixture
def node_id(store: Store) -> str:
    return store.create_node(project_id=PROJECT, kind=NodeKind.SLICE, title="n").id


def test_a_valid_decision_passes(store: Store, node_id: str) -> None:
    entry = store.journal_issue(
        node_id,
        kind=CommandKind.SQ_RUN,
        parameters=dict.fromkeys(REQUIRED_PARAMETER_KEYS[CommandKind.SQ_RUN], "v"),
    )
    store.journal_resolve(entry.id, outcome=JournalOutcome.COMPLETED)
    _check(
        store,
        _decision(node_id, journal_entry_id=entry.id),
        effect=StatusEffect(NodeStatus.DONE),
        attempt_step="P5",
    )


@pytest.mark.parametrize(
    "field", ["project_id", "rule_id", "table_version", "amoeba_version"]
)
def test_an_empty_text_field_raises(store: Store, node_id: str, field: str) -> None:
    with pytest.raises(ValueError, match=field):
        _check(store, _decision(node_id, **{field: " "}))


def test_unserializable_json_raises(store: Store, node_id: str) -> None:
    with pytest.raises(ValueError, match="inputs"):
        _check(store, _decision(node_id, inputs={"x": object()}))
    with pytest.raises(ValueError, match="route_parameters"):
        _check(store, _decision(node_id, route_parameters={"x": object()}))


def test_an_empty_attempt_step_raises(store: Store, node_id: str) -> None:
    with pytest.raises(ValueError, match="attempt_step"):
        _check(store, _decision(node_id), attempt_step="")


def test_a_mismatched_table_version_raises(store: Store, node_id: str) -> None:
    with pytest.raises(ValueError, match="does not match"):
        _check(store, _decision(node_id), table=RoutingTableVersion("v2", "rules"))


def test_an_unknown_route_raises(store: Store, node_id: str) -> None:
    with pytest.raises(ValueError):
        _check(store, _decision(node_id, route="sideways"))


def test_a_node_outside_the_project_or_missing_raises(store: Store) -> None:
    other = store.create_node(project_id="other", kind=NodeKind.SLICE, title="n").id
    for node in (other, "no-such-node"):
        with pytest.raises(NodeNotFoundError):
            _check(store, _decision(node))


def test_a_missing_entry_or_one_in_another_project_raises(
    store: Store, node_id: str
) -> None:
    other_node = store.create_node(project_id="other", kind=NodeKind.SLICE, title="n")
    foreign = store.journal_issue(
        other_node.id,
        kind=CommandKind.SQ_RUN,
        parameters=dict.fromkeys(REQUIRED_PARAMETER_KEYS[CommandKind.SQ_RUN], "v"),
    )
    for entry_id in ("no-such-entry", foreign.id):
        with pytest.raises(InvalidTransitionError):
            _check(store, _decision(node_id, journal_entry_id=entry_id))


@pytest.mark.parametrize(
    "status", [NodeStatus.BLOCKED_ON_HUMAN, NodeStatus.BLOCKED_ON_JUDGE]
)
def test_a_blocked_status_effect_is_refused(
    store: Store, node_id: str, status: NodeStatus
) -> None:
    with pytest.raises(InvalidTransitionError):
        _check(store, _decision(node_id), effect=StatusEffect(status))
