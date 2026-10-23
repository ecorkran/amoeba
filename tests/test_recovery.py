"""Tests for the reconcile loop, using in-test observers.

The reconcile logic is proved here independently of any real upstream: the
observers are defined in this file and return whichever observation the test
asks for. What matters is that each observation maps to the right outcome, that
every ambiguity escalates, and — the load-bearing one — that an interrupted
recovery re-run reconciles each entry exactly once.
"""

from __future__ import annotations

import os
import shutil
import sqlite3
from collections.abc import Mapping
from contextlib import closing
from pathlib import Path
from typing import NoReturn

import pytest
from sq_run_fixtures import (
    LEGACY_ENTRY_ID,
    insert_legacy_sq_run_entry,
    sq_run_parameters,
)
from sq_stub import write_outcome_document, write_sq_stub

from amoeba.process.observers import sq_runs
from amoeba.process.recovery import (
    Adopt,
    InFlight,
    NotApplied,
    Observation,
    Observer,
    ObserverRegistry,
    RecoverySummary,
    Unknown,
    reconcile,
)
from amoeba.process.settings import ProcessSettings
from amoeba.process.sq_outcome import RunOutcome
from amoeba.process.supervisor import build_observer_registry, recover_every_project
from amoeba.store import (
    BlockedKind,
    CommandKind,
    JournalEntry,
    JournalOutcome,
    JournalResolver,
    Node,
    NodeKind,
    NodeStatus,
    Store,
)

PROJECT = "demo"

SQ_PARAMETERS: dict[str, object] = sq_run_parameters(
    {"pipeline": "p6", "params": {"slice": "102"}}
)
CF_PARAMETERS: dict[str, object] = {"project": "amoeba", "expected": {"phase": "6"}}


class FixedObserver:
    """Returns one prepared observation, and records what it was asked about."""

    def __init__(self, observation: Observation) -> None:
        self._observation = observation
        self.seen: list[str] = []

    def observe(self, entry: JournalEntry) -> Observation:
        self.seen.append(entry.id)
        return self._observation


class PerEntryObserver:
    """Returns a different observation per entry id, keyed by issue order."""

    def __init__(self, observations: Mapping[str, Observation]) -> None:
        self._observations = observations
        self.seen: list[str] = []

    def observe(self, entry: JournalEntry) -> Observation:
        self.seen.append(entry.id)
        return self._observations[entry.id]


class RaisingObserver:
    """Raises on a named entry, to prove recovery aborts rather than swallowing.

    Entries before the failure get ``before``, so a test can choose whether the
    interrupted pass leaves resolutions or escalations behind it.
    """

    def __init__(self, raise_on: str, before: Observation | None = None) -> None:
        self._raise_on = raise_on
        self._before = before if before is not None else NotApplied(reason="fine")
        self.seen: list[str] = []

    def observe(self, entry: JournalEntry) -> Observation:
        self.seen.append(entry.id)
        if entry.id == self._raise_on:
            raise RuntimeError("observer exploded")
        return self._before


def _registry(
    observer: Observer, kind: CommandKind = CommandKind.SQ_RUN
) -> ObserverRegistry:
    return {kind: observer}


@pytest.fixture
def node(store: Store) -> Node:
    """A runnable node to journal commands against."""
    return store.create_node(
        project_id=PROJECT, kind=NodeKind.SLICE, title="recoverable"
    )


def _issue(store: Store, node_id: str, kind: CommandKind = CommandKind.SQ_RUN) -> str:
    """Journal one unresolved entry and return its id."""
    parameters = SQ_PARAMETERS if kind is CommandKind.SQ_RUN else CF_PARAMETERS
    return store.journal_issue(node_id, kind=kind, parameters=parameters).id


def _open_blocked_state_count(store: Store, node_id: str) -> int:
    return sum(
        1 for state in store.all_blocked_states(node_id) if not state.is_resolved
    )


# --------------------------------------------------------------------------
# Each observation type maps to its outcome
# --------------------------------------------------------------------------


def test_adopt_resolves_the_entry_as_adopted(store: Store, node: Node) -> None:
    """The observed effect is recorded, with recovery as the resolver."""
    entry_id = _issue(store, node.id)
    result: dict[str, object] = {"run_id": "run-1", "schema_version": 4}

    summary = reconcile(store, PROJECT, _registry(FixedObserver(Adopt(result=result))))

    reloaded = store.journal_entry(entry_id)
    assert reloaded is not None
    assert reloaded.outcome is JournalOutcome.ADOPTED
    assert reloaded.result == result
    assert reloaded.resolved_by is JournalResolver.RECOVERY
    assert summary == RecoverySummary(adopted=1)


def test_not_applied_resolves_the_entry_as_not_applied(
    store: Store, node: Node
) -> None:
    """A command that demonstrably did not land is closed, not escalated."""
    entry_id = _issue(store, node.id)

    summary = reconcile(
        store,
        PROJECT,
        _registry(FixedObserver(NotApplied(reason="cf holds the old value"))),
    )

    reloaded = store.journal_entry(entry_id)
    assert reloaded is not None
    assert reloaded.outcome is JournalOutcome.NOT_APPLIED
    assert reloaded.resolved_by is JournalResolver.RECOVERY

    reloaded_node = store.get_node(node.id)
    assert reloaded_node is not None
    assert reloaded_node.status is NodeStatus.RUNNABLE
    assert summary == RecoverySummary(not_applied=1)


def test_unknown_escalates_and_blocks_the_node(store: Store, node: Node) -> None:
    """Every ambiguity becomes a human decision, carrying the entry."""
    entry_id = _issue(store, node.id)

    summary = reconcile(
        store, PROJECT, _registry(FixedObserver(Unknown(reason="2 candidate runs")))
    )

    reloaded = store.journal_entry(entry_id)
    assert reloaded is not None
    assert reloaded.outcome is JournalOutcome.UNKNOWN
    assert reloaded.resolved_by is JournalResolver.RECOVERY

    reloaded_node = store.get_node(node.id)
    assert reloaded_node is not None
    assert reloaded_node.status is NodeStatus.BLOCKED_ON_HUMAN

    blocked_state = store.blocked_state_for(node.id)
    assert blocked_state is not None
    assert blocked_state.kind is BlockedKind.HUMAN
    assert entry_id in blocked_state.context
    assert "2 candidate runs" in blocked_state.context
    assert summary == RecoverySummary(unknown=1)


def test_unknown_candidates_are_named_in_the_blocked_context(
    store: Store, node: Node
) -> None:
    """A human reading the block sees what the observer actually saw."""
    _issue(store, node.id)

    reconcile(
        store,
        PROJECT,
        _registry(
            FixedObserver(Unknown(reason="2 candidates", candidates=("run-a", "run-b")))
        ),
    )

    blocked_state = store.blocked_state_for(node.id)
    assert blocked_state is not None
    assert "run-a" in blocked_state.context
    assert "run-b" in blocked_state.context


# --------------------------------------------------------------------------
# Missing observer, and the already-blocked node
# --------------------------------------------------------------------------


def test_a_kind_with_no_registered_observer_escalates(store: Store, node: Node) -> None:
    """A missing observer is Unknown — never an error and never a skip."""
    entry_id = _issue(store, node.id, kind=CommandKind.CF_WRITE)

    summary = reconcile(store, PROJECT, {})

    reloaded = store.journal_entry(entry_id)
    assert reloaded is not None
    assert reloaded.outcome is JournalOutcome.UNKNOWN

    reloaded_node = store.get_node(node.id)
    assert reloaded_node is not None
    assert reloaded_node.status is NodeStatus.BLOCKED_ON_HUMAN

    blocked_state = store.blocked_state_for(node.id)
    assert blocked_state is not None
    assert "no observer registered" in blocked_state.context
    assert summary == RecoverySummary(unknown=1)


def test_an_empty_registry_does_not_skip_entries(store: Store, node: Node) -> None:
    """Every entry is accounted for even when nothing can answer for it."""
    first = _issue(store, node.id)
    second = _issue(store, node.id)

    summary = reconcile(store, PROJECT, {})

    assert summary == RecoverySummary(unknown=2)
    assert store.unresolved_journal_entries(PROJECT) == []
    for entry_id in (first, second):
        entry = store.journal_entry(entry_id)
        assert entry is not None
        assert entry.outcome is JournalOutcome.UNKNOWN


def test_recovery_over_an_already_blocked_node_leaves_one_blocked_state(
    store: Store, node: Node
) -> None:
    """Two escalations against one node do not stack blocked states.

    The unique partial index forbids a second open blocked state; recovery
    must reach that outcome by branching, not by colliding with the index.
    """
    first = _issue(store, node.id)
    second = _issue(store, node.id)

    summary = reconcile(
        store, PROJECT, _registry(FixedObserver(Unknown(reason="ambiguous")))
    )

    assert summary == RecoverySummary(unknown=2)
    assert _open_blocked_state_count(store, node.id) == 1
    for entry_id in (first, second):
        entry = store.journal_entry(entry_id)
        assert entry is not None
        assert entry.outcome is JournalOutcome.UNKNOWN


# --------------------------------------------------------------------------
# Ordering, summary, and the empty case
# --------------------------------------------------------------------------


def test_entries_are_observed_oldest_first(store: Store, node: Node) -> None:
    """Recovery consumes the journal in issue order."""
    first = _issue(store, node.id)
    second = _issue(store, node.id)
    third = _issue(store, node.id)
    observer = FixedObserver(NotApplied(reason="none of them landed"))

    reconcile(store, PROJECT, _registry(observer))

    assert observer.seen == [first, second, third]


def test_summary_counts_match_what_was_written(store: Store, node: Node) -> None:
    """The startup log line reports what actually happened."""
    adopted_id = _issue(store, node.id)
    not_applied_id = _issue(store, node.id)
    unknown_id = _issue(store, node.id)

    observer = PerEntryObserver(
        {
            adopted_id: Adopt(result={"run_id": "run-1"}),
            not_applied_id: NotApplied(reason="never issued"),
            unknown_id: Unknown(reason="ambiguous"),
        }
    )

    summary = reconcile(store, PROJECT, _registry(observer))

    assert summary == RecoverySummary(adopted=1, not_applied=1, unknown=1)
    assert summary.total == 3
    assert summary.describe() == "1 adopted, 0 in_flight, 1 not_applied, 1 unknown"

    counted = {
        JournalOutcome.ADOPTED: 0,
        JournalOutcome.NOT_APPLIED: 0,
        JournalOutcome.UNKNOWN: 0,
    }
    for entry in store.journal_entries(PROJECT):
        assert entry.outcome is not None
        counted[entry.outcome] += 1
    assert counted == {
        JournalOutcome.ADOPTED: 1,
        JournalOutcome.NOT_APPLIED: 1,
        JournalOutcome.UNKNOWN: 1,
    }


def test_in_flight_leaves_the_entry_unresolved_and_is_counted(
    store: Store, node: Node, caplog: pytest.LogCaptureFixture
) -> None:
    entry_id = _issue(store, node.id)
    answer = InFlight(run_id="run-9", status=RunOutcome.PAUSED.value)

    with caplog.at_level("INFO"):
        summary = reconcile(store, PROJECT, _registry(FixedObserver(answer)))

    reloaded = store.journal_entry(entry_id)
    assert reloaded is not None
    assert not reloaded.is_resolved
    assert [e.id for e in store.unresolved_journal_entries(PROJECT)] == [entry_id]
    assert summary == RecoverySummary(in_flight=1)
    assert summary.total == 1
    assert summary.describe() == "0 adopted, 1 in_flight, 0 not_applied, 0 unknown"
    assert entry_id in caplog.text
    assert "run-9" in caplog.text
    assert "paused" in caplog.text


def test_nothing_to_reconcile_is_an_empty_summary(store: Store) -> None:
    """A clean journal is the common case, and says so."""
    summary = reconcile(
        store, PROJECT, _registry(FixedObserver(Unknown(reason="unused")))
    )

    assert summary == RecoverySummary()
    assert summary.total == 0
    assert summary.describe() == "nothing to reconcile"


def test_resolved_entries_are_not_revisited(store: Store, node: Node) -> None:
    """Recovery only ever looks at entries with a NULL outcome."""
    already_closed = _issue(store, node.id)
    store.journal_resolve(
        already_closed, outcome=JournalOutcome.COMPLETED, result={"run_id": "run-0"}
    )
    pending = _issue(store, node.id)
    observer = FixedObserver(NotApplied(reason="not issued"))

    reconcile(store, PROJECT, _registry(observer))

    assert observer.seen == [pending]
    closed = store.journal_entry(already_closed)
    assert closed is not None
    assert closed.outcome is JournalOutcome.COMPLETED


def test_recovery_is_project_scoped(store: Store, node: Node) -> None:
    """Another project's entries are not reconciled by this project's pass."""
    other_node = store.create_node(
        project_id="other", kind=NodeKind.SLICE, title="elsewhere"
    )
    other_entry = _issue(store, other_node.id)
    _issue(store, node.id)

    summary = reconcile(
        store, PROJECT, _registry(FixedObserver(NotApplied(reason="nope")))
    )

    assert summary == RecoverySummary(not_applied=1)
    untouched = store.journal_entry(other_entry)
    assert untouched is not None
    assert untouched.is_resolved is False


# --------------------------------------------------------------------------
# The crash-safety properties
# --------------------------------------------------------------------------


def test_interrupted_recovery_reconciles_each_entry_exactly_once(
    store: Store, node: Node
) -> None:
    """Per-entry transactions: a crash partway loses no work and repeats none.

    The first pass is interrupted by an observer that raises on the third of
    five entries. The re-run must pick up exactly the entries still unresolved
    — which is what fails if recovery batched the whole run into one
    transaction, because the first two resolutions would have rolled back.
    """
    entry_ids = [
        _issue(store, node.id),
        _issue(store, node.id),
        _issue(store, node.id),
        _issue(store, node.id),
        _issue(store, node.id),
    ]

    with pytest.raises(RuntimeError, match="observer exploded"):
        reconcile(store, PROJECT, _registry(RaisingObserver(raise_on=entry_ids[2])))

    # The first two committed; the interrupted one and those after it did not.
    assert [entry.id for entry in store.unresolved_journal_entries(PROJECT)] == (
        entry_ids[2:]
    )

    second_pass = FixedObserver(NotApplied(reason="observed on the re-run"))
    summary = reconcile(store, PROJECT, _registry(second_pass))

    assert second_pass.seen == entry_ids[2:]
    assert summary == RecoverySummary(not_applied=3)
    assert store.unresolved_journal_entries(PROJECT) == []

    # Each entry was reconciled exactly once: the first two still carry the
    # outcome from the first pass, untouched by the second.
    for entry_id in entry_ids:
        entry = store.journal_entry(entry_id)
        assert entry is not None
        assert entry.outcome is JournalOutcome.NOT_APPLIED
        assert entry.resolved_by is JournalResolver.RECOVERY


def test_interrupted_recovery_does_not_double_block(store: Store) -> None:
    """A re-run after an interrupted escalation leaves one blocked state each.

    Every entry escalates in both passes, so a node whose escalation committed
    in the first pass is escalated *again* in the second only if recovery
    wrongly revisits a resolved entry — which would collide with the unique
    partial index or stack a second open blocked state.
    """
    nodes = [
        store.create_node(project_id=PROJECT, kind=NodeKind.SLICE, title=f"n{index}")
        for index in range(3)
    ]
    entry_ids = [_issue(store, item.id) for item in nodes]
    escalate = Unknown(reason="ambiguous")

    with pytest.raises(RuntimeError):
        reconcile(
            store,
            PROJECT,
            _registry(RaisingObserver(raise_on=entry_ids[1], before=escalate)),
        )

    # The first node's escalation committed before the failure.
    assert _open_blocked_state_count(store, nodes[0].id) == 1

    reconcile(store, PROJECT, _registry(FixedObserver(escalate)))

    for item in nodes:
        assert _open_blocked_state_count(store, item.id) == 1


def test_a_raising_observer_aborts_recovery_and_propagates(
    store: Store, node: Node
) -> None:
    """An unexpected exception is never swallowed into a confident answer.

    Recovery that cannot complete must abort startup rather than let tenants
    run against unreconciled state, so the exception propagates unchanged.
    """
    first = _issue(store, node.id)
    second = _issue(store, node.id)

    with pytest.raises(RuntimeError, match="observer exploded"):
        reconcile(store, PROJECT, _registry(RaisingObserver(raise_on=second)))

    # The entry before the failure stays reconciled; the failing one stays open.
    resolved = store.journal_entry(first)
    assert resolved is not None
    assert resolved.outcome is JournalOutcome.NOT_APPLIED

    still_open = store.journal_entry(second)
    assert still_open is not None
    assert still_open.is_resolved is False


def test_a_raising_observer_leaves_the_remaining_entries_untouched(
    store: Store, node: Node
) -> None:
    """Entries after the failure are not reconciled by a partial pass."""
    _issue(store, node.id)
    failing = _issue(store, node.id)
    later = _issue(store, node.id)

    with pytest.raises(RuntimeError):
        reconcile(store, PROJECT, _registry(RaisingObserver(raise_on=failing)))

    entry = store.journal_entry(later)
    assert entry is not None
    assert entry.is_resolved is False


def test_recovery_calls_nothing_but_the_observer_and_the_store(
    store: Store, node: Node
) -> None:
    """Recovery never issues a command: the observer is its only outward call.

    Asserted structurally — the observer records every entry it was asked
    about, and the only writes that appear are the journal resolutions and the
    block. Nothing re-issues, because there is no path here that could.
    """
    entry_id = _issue(store, node.id)
    observer = FixedObserver(Adopt(result={"run_id": "run-1"}))

    reconcile(store, PROJECT, _registry(observer))

    assert observer.seen == [entry_id]
    entry = store.journal_entry(entry_id)
    assert entry is not None
    assert entry.outcome is JournalOutcome.ADOPTED
    # The node was not touched: adoption records a fact, it does not act on it.
    reloaded = store.get_node(node.id)
    assert reloaded is not None
    assert reloaded.status is NodeStatus.RUNNABLE


# --------------------------------------------------------------------------
# The shipped registry, against the stub `sq` (slice 120)
# --------------------------------------------------------------------------

LEGACY_RUN_FIXTURE = (
    Path(__file__).parent / "fixtures" / "sq_runs" / "run-20261015-p5-8a59ee89.json"
)
LEGACY_RUN_ID = "run-20261015-p5-8a59ee89"


def _stub_settings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, runs_dir: Path
) -> tuple[Path, ProcessSettings]:
    """The stub ``sq`` first on ``PATH`` under a scratch ``HOME``; no launch grace."""
    home = tmp_path / "home"
    home.mkdir()
    bin_dir = write_sq_stub(tmp_path / "bin")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    settings = ProcessSettings(sq_runs_dir=runs_dir, launch_grace_seconds=0.0)
    return home, settings


def _run_document(run_id: str, outcome: RunOutcome) -> dict[str, object]:
    return {"run_id": run_id, "outcome": outcome.value, "status": outcome.value}


def _issue_by_id(store: Store, node_id: str, run_id: str) -> str:
    return store.journal_issue(
        node_id,
        kind=CommandKind.SQ_RUN,
        parameters=sq_run_parameters({"pipeline": "p6", "params": {}}, run_id=run_id),
    ).id


def test_an_id_bearing_entry_with_a_stub_document_is_left_in_flight(
    store: Store, node: Node, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home, settings = _stub_settings(tmp_path, monkeypatch, tmp_path / "runs")
    write_outcome_document(home, _run_document("run-by-id-1", RunOutcome.PAUSED))
    entry_id = _issue_by_id(store, node.id, "run-by-id-1")

    summary = reconcile(store, PROJECT, build_observer_registry(settings))

    reloaded = store.journal_entry(entry_id)
    assert reloaded is not None
    assert not reloaded.is_resolved
    assert summary == RecoverySummary(in_flight=1)


def test_an_id_bearing_entry_with_no_run_state_past_grace_is_not_applied(
    store: Store, node: Node, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, settings = _stub_settings(tmp_path, monkeypatch, tmp_path / "runs")
    entry_id = _issue_by_id(store, node.id, "run-never-launched")

    summary = reconcile(store, PROJECT, build_observer_registry(settings))

    reloaded = store.journal_entry(entry_id)
    assert reloaded is not None
    assert reloaded.outcome is JournalOutcome.NOT_APPLIED
    assert summary == RecoverySummary(not_applied=1)


def test_a_legacy_row_still_recovers_through_the_matcher(
    store: Store, node: Node, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A pre-120 row has no run id, so the unchanged matcher reads the runs dir."""
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    shutil.copy(LEGACY_RUN_FIXTURE, runs_dir)
    _, settings = _stub_settings(tmp_path, monkeypatch, runs_dir)
    with closing(sqlite3.connect(store.path)) as connection:
        insert_legacy_sq_run_entry(
            connection,
            entry_id=LEGACY_ENTRY_ID,
            project_id=PROJECT,
            node_id=node.id,
            parameters={"pipeline": "p5", "params": {"slice": "176"}},
            issued_at="2026-10-15T22:00:00+00:00",
        )

    summary = reconcile(store, PROJECT, build_observer_registry(settings))

    reloaded = store.journal_entry(LEGACY_ENTRY_ID)
    assert reloaded is not None
    assert reloaded.outcome is JournalOutcome.ADOPTED
    assert reloaded.result is not None
    assert reloaded.result["run_id"] == LEGACY_RUN_ID
    assert summary == RecoverySummary(adopted=1)


def test_recovery_by_id_reads_no_run_state_file(
    store: Store, node: Node, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """D8: in-flight, not_applied and unknown answers, none from a run file.

    The runs directory holds a file that would match the entries, and the
    scanner and parser fail the test if they are called at all.
    """
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    shutil.copy(LEGACY_RUN_FIXTURE, runs_dir)
    home, settings = _stub_settings(tmp_path, monkeypatch, runs_dir)

    def _must_not_be_called(*_: object, **__: object) -> NoReturn:
        raise AssertionError("recovery by id read a run-state file")

    monkeypatch.setattr(sq_runs, "scan_runs_directory", _must_not_be_called)
    monkeypatch.setattr(sq_runs, "parse_run_file", _must_not_be_called)
    write_outcome_document(home, _run_document("run-adopt", RunOutcome.COMPLETED))
    write_outcome_document(home, _run_document("run-unreadable", RunOutcome.UNREADABLE))
    in_flight = _issue_by_id(store, node.id, "run-adopt")
    not_applied = _issue_by_id(store, node.id, "run-absent")
    unknown = _issue_by_id(store, node.id, "run-unreadable")

    recover_every_project([(PROJECT, store)], settings)

    outcomes = {
        entry_id: (entry.outcome if (entry := store.journal_entry(entry_id)) else None)
        for entry_id in (in_flight, not_applied, unknown)
    }
    assert outcomes == {
        in_flight: None,
        not_applied: JournalOutcome.NOT_APPLIED,
        unknown: JournalOutcome.UNKNOWN,
    }
