"""``record_runner_report`` completes a node in the same transaction as the report.

Slice 132, D4: a crash between resolving the entry and completing the node would
relaunch a run that had already finished.
"""

from __future__ import annotations

import pytest
from evidence_harness import seed_node
from fault_injection import InjectedFailureError, fail_on_node_status_write
from sq_run_fixtures import sq_run_parameters

from amoeba.store import CommandKind, JournalEntry, JournalOutcome, NodeStatus, Store

RUN_ID = "run-20261029-p456-aaaa1111"


def _issue(store: Store, node_id: str) -> JournalEntry:
    parameters = sq_run_parameters(
        {"pipeline": "p456", "params": {}, "project": "p", "checkout": "/work/p"},
        run_id=RUN_ID,
    )
    return store.journal_issue(node_id, kind=CommandKind.SQ_RUN, parameters=parameters)


def _report(store: Store, entry: JournalEntry, **options: str) -> None:
    store.record_runner_report(
        entry.id,
        [],
        outcome=JournalOutcome.COMPLETED,
        result={"run_id": RUN_ID},
        **options,
    )


def _status(store: Store, node_id: str) -> NodeStatus:
    node = store.get_node(node_id)
    assert node is not None
    return node.status


def test_the_option_resolves_the_entry_and_completes_the_node(store: Store) -> None:
    node_id = seed_node(store)
    entry = _issue(store, node_id)

    _report(store, entry, complete_node_id=node_id)

    resolved = store.journal_entry(entry.id)
    assert resolved is not None and resolved.is_resolved
    assert _status(store, node_id) is NodeStatus.DONE


def test_a_failed_node_write_leaves_neither_change_visible(
    store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    node_id = seed_node(store)
    entry = _issue(store, node_id)
    before = _status(store, node_id)
    fail_on_node_status_write(monkeypatch, store)

    with pytest.raises(InjectedFailureError):
        _report(store, entry, complete_node_id=node_id)

    unresolved = store.journal_entry(entry.id)
    assert unresolved is not None and not unresolved.is_resolved
    assert _status(store, node_id) is before


def test_without_the_option_the_node_status_is_untouched(store: Store) -> None:
    node_id = seed_node(store)
    entry = _issue(store, node_id)
    before = _status(store, node_id)

    _report(store, entry)

    assert _status(store, node_id) is before
