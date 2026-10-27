"""D3, D4 at tick level: the shipped table advances past a clear gate and checks."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from cf_stub_gates import STATUS_MODE_ENV, GateMode
from sq_stub_scripts import RunScript, single_review

from amoeba.inspection.checks import check_rows
from amoeba.inspection.listing import NODE_OPTION, ListingRequest
from amoeba.process import RunOutcome
from amoeba.runner.gates.outcome_record import OBS_GATE
from amoeba.runner.ingest.record import RESULT_OUTCOME_OBSERVATION
from amoeba.runner.lifecycle.plan_read import CF_KEY_REVIEW_GATE_EFFECTIVE_DATE
from amoeba.runner.lifecycle.steps import LifecycleStep
from amoeba.store import (
    CommandKind,
    JournalEntry,
    Node,
    NodeStatus,
    Route,
    RoutingDecision,
    Store,
)
from runner.dispatch.tick_rig import DispatchRig
from runner.gate_rig import (
    DESIGN_PATH,
    config_knobs,
    git_checkout,
    single_status_knobs,
    status_fixture,
    write_design,
    write_slice_list,
)
from runner.resolutions.resolution_support import resolve_block
from runner.routing.table_support import shipped_table

INDEX = 125  # an index the stub CF state can point at
CF_SLUG = "run-dispatch-and-outcome-ingestion"
STATED_CONCERNS = "verdict: CONCERNS"
PASS = "verdict: PASS"
ADVANCE = "advance-on-stated-pass"
CATCH_ALL = "escalate-everything-else"


@pytest.fixture
def rig(tmp_path: Path, store: Store) -> Iterator[DispatchRig]:
    built = DispatchRig(tmp_path, store)
    built.tick_rig.routing_table = shipped_table()
    yield built


class Outcome:
    """One completed run of ``step`` after the stub CF answered as arranged."""

    def __init__(
        self, slice_node: Node, node: Node, entry: JournalEntry, rig: DispatchRig
    ) -> None:
        self.slice_node = slice_node
        self.node = node
        self.entry = entry
        self.rig = rig

    @property
    def decision(self) -> RoutingDecision:
        [decision] = self.rig.store.routing_decisions(self.node.id)
        return decision

    def result(self) -> dict[str, Any]:
        done = self.rig.store.journal_entry(self.entry.id)
        assert done is not None and done.result is not None
        return dict(done.result)

    def checks(self) -> dict[str, str]:
        found = self.rig.store.checks("demo", node_id=self.slice_node.id)
        return {c.name: c.standing.value for c in found}


def _review(rig: DispatchRig, verdict: str, *, derived: bool = False) -> RunScript:
    script = single_review(CF_SLUG)
    files = {
        path: text.replace(STATED_CONCERNS, verdict, 1).replace(
            "verdictSource: stated",
            "verdictSource: derived" if derived else "verdictSource: stated",
        )
        for path, text in script.files.items()
    }
    for relative, text in files.items():
        target = rig.world.root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    return RunScript(files, script.document)


def _complete(
    rig: DispatchRig,
    tmp_path: Path,
    *,
    step: LifecycleStep,
    status: str,
    verdict: str = PASS,
    derived: bool = False,
    front: dict[str, str] | None = None,
    effective: str = "",
    listed: bool = True,
    design_on_disk: bool = True,
    gate_mode: GateMode | None = None,
) -> Outcome:
    """Run ``step`` to completion with CF's answers as given; return what was routed."""
    slice_node, node = rig.slice_and_step("routed", INDEX, step)
    assert slice_node.parent_id is not None
    initiative = rig.store.get_node(slice_node.parent_id)
    assert initiative is not None and initiative.cf.index is not None
    checkout = git_checkout(rig.world.root)
    if design_on_disk:
        write_design(checkout, DESIGN_PATH, front)
    fixture = status_fixture(tmp_path / "status.json", status, INDEX)
    knobs = {
        **write_slice_list(
            tmp_path / "plan",
            initiative.cf.index,
            {INDEX: DESIGN_PATH} if listed else {},
        ),
        **single_status_knobs(fixture),
        **config_knobs(tmp_path, {CF_KEY_REVIEW_GATE_EFFECTIVE_DATE: effective}),
    }
    rig.tick_rig.gate_run = rig.world.run(knobs)
    rig.tick()  # the pointer write
    rig.tick()  # the launch
    if gate_mode is not None:
        # The gate fails only for the outcome observation: the launch has happened.
        rig.tick_rig.gate_run = rig.world.run(
            {**knobs, STATUS_MODE_ENV: gate_mode.value}
        )
    review = _review(rig, verdict, derived=derived)
    entry = rig.run_of(node)
    rig.end_run(node, RunOutcome.COMPLETED, **review.document)
    return Outcome(slice_node, node, entry, rig)


def test_a_tasks_pass_with_cf_in_implementation_advances(
    rig: DispatchRig, tmp_path: Path
) -> None:
    out = _complete(rig, tmp_path, step=LifecycleStep.TASKS, status="in_implementation")

    assert (out.decision.rule_id, out.decision.route) == (ADVANCE, Route.ADVANCE)
    assert out.decision.inputs["gate_state"] == "clear"
    assert out.decision.inputs["check_standing"] == "passed"
    assert rig.status(out.node) is NodeStatus.DONE


def test_a_tasks_pass_that_cf_fails_at_the_tasks_gate_escalates(
    rig: DispatchRig, tmp_path: Path
) -> None:
    out = _complete(
        rig, tmp_path, step=LifecycleStep.TASKS, status="review_failed_tasks"
    )

    assert (out.decision.rule_id, out.decision.route) == (CATCH_ALL, Route.ESCALATE)
    assert out.decision.inputs["gate_state"] == "review_failed"
    assert rig.status(out.node) is not NodeStatus.DONE


def test_derived_pass_cleared_by_cf_escalates(rig: DispatchRig, tmp_path: Path) -> None:
    out = _complete(
        rig,
        tmp_path,
        step=LifecycleStep.TASKS,
        status="in_implementation",
        derived=True,
    )

    assert out.decision.inputs["gate_state"] == "clear", "CF's gate clears"
    assert out.decision.inputs["standing"] == "derived"
    assert out.decision.route is Route.ESCALATE, "CF's clear is not enough alone"


def test_a_pending_decision_after_p4_escalates_with_the_decisions_in_the_result(
    rig: DispatchRig, tmp_path: Path
) -> None:
    out = _complete(
        rig, tmp_path, step=LifecycleStep.SLICE_DESIGN, status="pending_decision"
    )

    assert out.decision.inputs["gate_state"] == "pending_decision"
    assert out.decision.route is Route.ESCALATE
    gate = out.result()[RESULT_OUTCOME_OBSERVATION][OBS_GATE]
    assert gate["pending_decisions"] == [{"heading": "Decision", "line": 12}]


def test_p6_with_cf_still_in_implementation_escalates_as_misplaced(
    rig: DispatchRig, tmp_path: Path
) -> None:
    out = _complete(
        rig, tmp_path, step=LifecycleStep.IMPLEMENTATION, status="in_implementation"
    )

    assert out.decision.inputs["gate_state"] == "misplaced"
    assert out.decision.route is Route.ESCALATE


def test_a_failed_gate_read_escalates_as_unknown(
    rig: DispatchRig, tmp_path: Path
) -> None:
    out = _complete(
        rig,
        tmp_path,
        step=LifecycleStep.TASKS,
        status="in_implementation",
        gate_mode=GateMode.FAIL,
    )

    assert out.decision.inputs["gate_state"] == "unknown"
    assert out.decision.route is Route.ESCALATE


def test_review_none_check_failed_and_escalates(
    rig: DispatchRig, tmp_path: Path
) -> None:
    out = _complete(
        rig,
        tmp_path,
        step=LifecycleStep.TASKS,
        status="in_implementation",
        front={"review": "none"},
    )

    assert out.checks() == {
        "ungate_review_none": "failed",
        "ungate_effective_date": "passed",
    }
    assert out.decision.inputs["check_standing"] == "failed"
    assert out.decision.route is Route.ESCALATE
    rows = check_rows(
        rig.store, ListingRequest("demo", {NODE_OPTION.name: out.slice_node.id}, False)
    )
    by_name = {row["name"]: row for row in rows}
    hatch = by_name["ungate_review_none"]
    assert hatch["source_path"] == DESIGN_PATH
    assert hatch["examined"] == {"design_path": DESIGN_PATH, "review": "none"}
    assert hatch["standing"] == "failed"


def test_an_early_date_created_escalates(rig: DispatchRig, tmp_path: Path) -> None:
    out = _complete(
        rig,
        tmp_path,
        step=LifecycleStep.TASKS,
        status="in_implementation",
        front={"dateCreated": "20200101"},
        effective="20261020",
    )

    assert out.checks()["ungate_effective_date"] == "failed"
    assert out.decision.route is Route.ESCALATE


def test_a_missing_design_escalates_with_both_checks_vacuous(
    rig: DispatchRig, tmp_path: Path
) -> None:
    out = _complete(
        rig,
        tmp_path,
        step=LifecycleStep.TASKS,
        status="in_implementation",
        design_on_disk=False,
    )

    assert out.checks() == {
        "ungate_review_none": "vacuous",
        "ungate_effective_date": "vacuous",
    }
    assert out.decision.inputs["check_standing"] == "vacuous"
    assert out.decision.route is Route.ESCALATE


def test_a_pm_accept_of_a_hatch_escalation_advances_the_step(
    rig: DispatchRig, tmp_path: Path
) -> None:
    out = _complete(
        rig,
        tmp_path,
        step=LifecycleStep.TASKS,
        status="in_implementation",
        front={"review": "none"},
    )
    assert out.decision.route is Route.ESCALATE
    blocked = rig.store.blocked_state_for(out.node.id)
    assert blocked is not None

    resolve_block(rig.store, blocked.id, "accept", project_id="demo")
    rig.tick()

    assert rig.status(out.node) is NodeStatus.DONE
    runs = rig.entries(CommandKind.SQ_RUN, out.node)
    assert len(runs) == 1, "a store-only accept: no rerun"
