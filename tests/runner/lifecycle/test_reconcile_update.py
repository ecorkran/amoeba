"""The update rule: references follow CF; titles and links never change."""

from __future__ import annotations

import logging
from collections.abc import Iterator

import pytest

from amoeba.runner.faults import TickFaults
from amoeba.runner.lifecycle.plan_read import PlanRead
from amoeba.runner.lifecycle.reconcile import reconcile
from amoeba.store import Store
from amoeba.store.inbox_models import Channel
from amoeba.store.models import Node, NodeKind

from .reconcile_support import cf_initiative, cf_slice, plan, slice_list
from .tree_support import CF_PROJECT, PROJECT

OLD_FILE = "project-documents/user/slices/121-slice.old-name.md"
NEW_FILE = "project-documents/user/slices/121-slice.new-name.md"


@pytest.fixture
def store() -> Iterator[Store]:
    with Store.open_temporary() as opened:
        yield opened


def _read(
    *,
    arch_file: str | None = "120-arch.y.md",
    design_file: str | None = OLD_FILE,
    slice_title: str = "Slice 121",
    initiative_title: str = "Initiative 120",
) -> PlanRead:
    return plan(
        cf_initiative(120, name=initiative_title, arch_file=arch_file),
        slices={
            120: slice_list(
                cf_slice(121, name=slice_title, design_file=design_file),
            )
        },
    )


def _run(store: Store, read: PlanRead) -> bool:
    return reconcile(store, PROJECT, CF_PROJECT, read, TickFaults())


def _node(store: Store, kind: NodeKind, index: int) -> Node:
    [node] = [
        n
        for n in store.nodes_for_project(PROJECT)
        if n.kind is kind and n.cf.index == index
    ]
    return node


def test_a_renamed_slice_keeps_its_node_and_link_and_raises_no_orphan(
    store: Store,
) -> None:
    _run(store, _read())
    before = _node(store, NodeKind.SLICE, 121)

    wrote = _run(store, _read(design_file=NEW_FILE))

    after = _node(store, NodeKind.SLICE, 121)
    assert wrote
    assert after.id == before.id and after.cf.index == 121
    assert after.cf.slice_name == "new-name" and after.cf.artifact_path == NEW_FILE
    assert store.messages(PROJECT, channel=Channel.ESCALATION) == []
    assert after.status is before.status


def test_a_changed_design_file_updates_both_fields_and_keeps_the_rest(
    store: Store,
) -> None:
    _run(store, _read())
    before = _node(store, NodeKind.SLICE, 121)

    _run(store, _read(design_file=NEW_FILE))

    after = _node(store, NodeKind.SLICE, 121)
    assert after.cf.project == before.cf.project
    assert after.cf.index == before.cf.index
    assert after.cf.phase == before.cf.phase


def test_a_changed_arch_file_updates_an_initiative(store: Store) -> None:
    _run(store, _read())

    wrote = _run(store, _read(arch_file="120-arch.renamed.md"))

    initiative = _node(store, NodeKind.INITIATIVE, 120)
    assert wrote and initiative.cf.artifact_path == "120-arch.renamed.md"


def test_an_unchanged_read_writes_nothing(store: Store) -> None:
    _run(store, _read())
    before = store.nodes_for_project(PROJECT)

    assert not _run(store, _read())
    assert store.nodes_for_project(PROJECT) == before


def test_a_changed_title_alone_updates_nothing(store: Store) -> None:
    _run(store, _read())
    before = store.nodes_for_project(PROJECT)

    wrote = _run(store, _read(slice_title="Retitled", initiative_title="Retitled too"))

    assert not wrote
    assert store.nodes_for_project(PROJECT) == before
    assert _node(store, NodeKind.SLICE, 121).title == "Slice 121"


def test_cf_reporting_no_file_does_not_clear_the_existing_values(
    store: Store,
) -> None:
    _run(store, _read())
    before = _node(store, NodeKind.SLICE, 121)

    wrote = _run(store, _read(arch_file=None, design_file=None))

    assert not wrote
    assert _node(store, NodeKind.SLICE, 121) == before
    assert _node(store, NodeKind.INITIATIVE, 120).cf.artifact_path == "120-arch.y.md"


def test_an_odd_new_file_updates_the_path_keeps_the_name_and_warns(
    store: Store, caplog: pytest.LogCaptureFixture
) -> None:
    _run(store, _read())

    with caplog.at_level(logging.WARNING):
        _run(store, _read(design_file="notes/design.txt"))

    node = _node(store, NodeKind.SLICE, 121)
    assert node.cf.artifact_path == "notes/design.txt"
    assert node.cf.slice_name == "old-name"
    assert any("notes/design.txt" in r.getMessage() for r in caplog.records)
