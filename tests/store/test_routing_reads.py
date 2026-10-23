"""D5-D7 reads: decisions, table versions and attempt counts."""

from __future__ import annotations

import json
from pathlib import Path

from amoeba.store import (
    REQUIRED_PARAMETER_KEYS,
    CommandKind,
    NodeKind,
    Route,
    RoutingDecision,
    RoutingTableVersion,
    Store,
    sql_runner,
)

PROJECT = "demo"
STAGED = ("2026-10-22T00:00:00+00:00", "2026-10-22T01:00:00+00:00")


def _node(store: Store) -> str:
    return store.create_node(project_id=PROJECT, kind=NodeKind.SLICE, title="n").id


def _stage_version(store: Store, version: str = "v1") -> None:
    store._connection.execute(  # pyright: ignore[reportPrivateUsage]
        sql_runner.INSERT_TABLE_VERSION, (version, "table text", STAGED[0])
    )


def _stage_decision(
    store: Store,
    decision_id: str,
    node_id: str,
    decided_at: str,
    *,
    entry_id: str | None = None,
    attempt: tuple[str, int] | None = None,
) -> None:
    step, count = attempt if attempt else (None, None)
    store._connection.execute(  # pyright: ignore[reportPrivateUsage]
        sql_runner.INSERT_DECISION,
        (decision_id, PROJECT, node_id, entry_id, json.dumps({"k": 1}), "rule-1")
        + ("v1", "0.1", Route.ADVANCE.value, json.dumps({"limit": 3}), step)
        + (count, decided_at),
    )


def test_every_read_is_empty_on_a_fresh_store(store: Store) -> None:
    node_id = _node(store)

    assert store.routing_decision("d") is None
    assert store.routing_decision_for_entry("j") is None
    assert store.routing_decisions(node_id) == []
    assert store.routing_table_version("v1") is None
    assert store.attempt_count(node_id, "P5") == 0


def test_reads_return_the_mapped_rows(store: Store) -> None:
    node_id = _node(store)
    _stage_version(store)
    _stage_decision(store, "d-late", node_id, STAGED[1])
    _stage_decision(store, "d-early", node_id, STAGED[0], attempt=("P5", 1))
    store._connection.execute(  # pyright: ignore[reportPrivateUsage]
        sql_runner.UPSERT_ATTEMPT_COUNT, (node_id, "P5", STAGED[0])
    )

    version = store.routing_table_version("v1")
    assert isinstance(version, RoutingTableVersion)
    assert version.content == "table text" and version.first_used_at is not None
    decision = store.routing_decision("d-early")
    assert isinstance(decision, RoutingDecision)
    assert decision.route is Route.ADVANCE
    assert decision.inputs == {"k": 1} and decision.route_parameters == {"limit": 3}
    assert (decision.attempt_step, decision.attempt_count) == ("P5", 1)
    assert [d.id for d in store.routing_decisions(node_id)] == ["d-early", "d-late"]
    assert store.attempt_count(node_id, "P5") == 1
    assert store.attempt_count(node_id, "P6") == 0


def test_a_decision_is_found_by_its_entry(store: Store) -> None:
    node_id = _node(store)
    _stage_version(store)
    entry_id = store.journal_issue(
        node_id,
        kind=CommandKind.SQ_RUN,
        parameters=dict.fromkeys(REQUIRED_PARAMETER_KEYS[CommandKind.SQ_RUN], "v"),
    ).id
    _stage_decision(store, "d-1", node_id, STAGED[0], entry_id=entry_id)

    found = store.routing_decision_for_entry(entry_id)

    assert found is not None and found.id == "d-1"
    assert found.journal_entry_id == entry_id


def test_every_read_works_through_a_read_only_handle(store_file: Path) -> None:
    with Store.open(store_file) as store:
        node_id = _node(store)
        _stage_version(store)
        _stage_decision(store, "d-1", node_id, STAGED[0])
        store._connection.commit()  # pyright: ignore[reportPrivateUsage]

    with Store.open_read_only(store_file) as reader:
        assert reader.routing_decision("d-1") is not None
        assert reader.routing_decisions(node_id) != []
        assert reader.routing_table_version("v1") is not None
        assert reader.routing_decision_for_entry("none") is None
        assert reader.attempt_count(node_id, "P5") == 0
