"""Plan-read faults in the project tick: raising, repeating, closing, isolating."""

from __future__ import annotations

from pathlib import Path

import pytest

from amoeba.store import NodeKind, Store
from amoeba.store.inbox_models import Channel
from runner.observe_support import CfReply
from runner.plan_tick_support import (
    ERROR_DOCUMENT,
    INITIATIVES_KEY,
    initiatives_json,
    serve_plan,
    slices_key,
)
from runner.tick_support import PLAN_READ_INTERVAL, PROJECT, Rig, link

LINK = "cf-1"
FAULT = "plan_read_failed"


@pytest.fixture
def rig(tmp_path: Path, store: Store) -> Rig:
    built = Rig(tmp_path, store)
    built.planners = ()
    link(store, "s-1", LINK, PROJECT)
    serve_plan(built.cf, (100,), {100: (101,)})
    return built


def _open_kinds(store: Store) -> list[str | None]:
    return [m.fault_kind for m in store.open_project_escalations(PROJECT)]


def _linked_indexes(store: Store, kind: NodeKind) -> list[int]:
    return sorted(
        n.cf.index
        for n in store.nodes_for_project(PROJECT)
        if n.kind is kind and n.cf.index is not None
    )


def _later(rig: Rig) -> None:
    rig.clock.seconds += PLAN_READ_INTERVAL
    rig.tick()


def test_a_failed_plan_read_stays_open_until_a_read_of_that_link_succeeds(
    rig: Rig, store: Store
) -> None:
    rig.tick()  # a good first read, so the probe has passed
    serve_plan(rig.cf, (100,), {100: (101,)})
    rig.cf.replies[slices_key(100)] = CfReply("", 1, ERROR_DOCUMENT)  # linked slices
    _later(rig)
    assert _open_kinds(store) == [FAULT]

    _later(rig)  # fails again: the same open row, no new one
    assert _open_kinds(store) == [FAULT]
    assert len(store.messages(PROJECT, channel=Channel.ESCALATION)) == 1

    serve_plan(rig.cf, (100,), {100: (101,)})
    _later(rig)
    assert _open_kinds(store) == []


def test_a_cut_off_tick_does_not_close_a_failing_links_fault(
    rig: Rig, store: Store
) -> None:
    rig.tick()
    rig.cf.replies[slices_key(100)] = CfReply("", 1, ERROR_DOCUMENT)
    _later(rig)
    assert _open_kinds(store) == [FAULT]

    rig.deadline = 0.0
    rig.clock.seconds += PLAN_READ_INTERVAL
    rig.tick()

    assert _open_kinds(store) == [FAULT]


def test_an_empty_list_with_linked_nodes_raises_a_fault_and_orphans_nothing(
    rig: Rig, store: Store
) -> None:
    rig.tick()
    before = store.nodes_for_project(PROJECT)
    rig.cf.replies[INITIATIVES_KEY] = CfReply("[]")

    _later(rig)

    assert _open_kinds(store) == [FAULT]
    assert store.nodes_for_project(PROJECT) == before


def test_a_duplicate_initiative_index_raises_a_fault_and_creates_nothing(
    rig: Rig, store: Store
) -> None:
    rig.cf.replies[INITIATIVES_KEY] = CfReply(initiatives_json(100, 100))

    rig.tick()

    assert _open_kinds(store) == [FAULT]
    assert store.nodes_for_project(PROJECT) == []


def test_a_slice_read_error_with_linked_slices_raises_a_fault_and_orphans_nothing(
    rig: Rig, store: Store
) -> None:
    rig.tick()
    before = store.nodes_for_project(PROJECT)
    rig.cf.replies[slices_key(100)] = CfReply("", 1, ERROR_DOCUMENT)

    _later(rig)

    assert _open_kinds(store) == [FAULT]
    assert store.nodes_for_project(PROJECT) == before


def test_a_failed_slice_read_leaves_another_initiatives_slices_applied(
    rig: Rig, store: Store
) -> None:
    serve_plan(rig.cf, (100, 200), {100: (101,), 200: (201,)})
    rig.tick()
    rig.cf.replies[slices_key(100)] = CfReply("", 2, "boom")
    serve_plan_200 = CfReply(
        '{"entries":[{"index":201,"name":"s","isChecked":false},'
        '{"index":202,"name":"s","isChecked":false}]}'
    )
    rig.cf.replies[slices_key(200)] = serve_plan_200

    _later(rig)

    assert _linked_indexes(store, NodeKind.SLICE) == [101, 201, 202]
    assert _open_kinds(store) == [FAULT]


def test_a_repeating_fault_adds_no_rows(rig: Rig, store: Store) -> None:
    rig.tick()
    rig.cf.replies[INITIATIVES_KEY] = CfReply("[]")

    for _ in range(4):
        _later(rig)

    assert len(store.messages(PROJECT, channel=Channel.ESCALATION)) == 1


def test_a_failed_initiatives_read_raises_one_fault_and_closes_on_the_next_success(
    rig: Rig, store: Store
) -> None:
    rig.tick()  # the link's probe passes once and is remembered for the lifetime
    before = store.nodes_for_project(PROJECT)
    rig.cf.replies[INITIATIVES_KEY] = CfReply("", 1, "cf exploded")

    _later(rig)
    _later(rig)

    assert _open_kinds(store) == [FAULT]
    assert len(store.messages(PROJECT, channel=Channel.ESCALATION)) == 1
    assert store.nodes_for_project(PROJECT) == before

    serve_plan(rig.cf, (100,), {100: (101,)})
    _later(rig)

    assert _open_kinds(store) == []
