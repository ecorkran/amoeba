"""Rig helpers for the gate tests: a real git checkout, a design, a status fixture.

They build the pieces the stub ``cf`` reads (``tests/cf_stub_gates.py``) and return the
environment knobs a ``CfWorld.run`` / ``DispatchRig.use_world`` call takes.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING

from cf_stub import PLAN_DIR_ENV
from cf_stub_gates import (
    CONFIG_ENV,
    STATUS_FIXTURE_ENV,
    STATUS_MAP_ENV,
    write_config_values,
    write_status_map,
)

from amoeba.runner.gates.cf_status import EXIT_GATE, GatePosition
from amoeba.runner.gates.hatches import DesignText, hatch_checks
from amoeba.runner.gates.outcome import (
    GateRead,
    OutcomeObservation,
    ReadFailed,
    unobservable,
)
from amoeba.runner.lifecycle.plan_read import CF_KEY_REVIEW_GATE_EFFECTIVE_DATE
from amoeba.runner.lifecycle.steps import LifecycleStep
from amoeba.store import JournalEntry, Node
from runner.git_repo import commit_file, make_repo

if TYPE_CHECKING:
    # Only for the annotation: the dispatch rig imports this module.
    from runner.dispatch.tick_rig import DispatchRig

STATUS_FIXTURES = Path(__file__).parents[1] / "fixtures" / "cf" / "status"
DESIGN_PATH = "project-documents/user/slices/128-slice.gates.md"


def failed_reads(entry: JournalEntry) -> OutcomeObservation:
    """An observation in which every read failed, for tests that ingest directly.

    Ingesting a ``completed`` run needs an observation; these tests do not care what
    CF said, only that the run is recorded.
    """
    return unobservable(entry, entry.node_id, "test: nothing was read", "amoeba-test")


CLEAR_FIXTURE = {
    LifecycleStep.SLICE_DESIGN: "needs_tasks",
    LifecycleStep.TASKS: "in_implementation_no_task_done",
    LifecycleStep.IMPLEMENTATION: "complete",
}


def clear_observation(
    entry: JournalEntry, node_id: str, step: LifecycleStep | None
) -> OutcomeObservation:
    """A healthy observation: CF's gate one past the step's exit, both hatches passed.

    For tests that stage an ingested outcome and route it through the shipped table.
    A step with no exit gate gets an unreadable gate, as it would in production.
    """
    exit_gate = None if step is None else EXIT_GATE.get(step)
    gate: GateRead | ReadFailed = (
        ReadFailed("test: the step has no exit gate")
        if exit_gate is None
        else GateRead(
            index=1,
            status="clear",
            review_type=None,
            position=GatePosition(exit_gate + 1),
            rationale=None,
            pending_decisions=None,
        )
    )
    design = DesignText(DESIGN_PATH, "---\ndateCreated: 20261026\n---\n\n# Design\n")
    return OutcomeObservation(
        gate=gate,
        design_path=DESIGN_PATH,
        design_failure=None,
        git=None,
        checks=hatch_checks(entry.id, node_id, design, "", "amoeba-test"),
    )


def clear_gates(
    rig: DispatchRig, slice_node: Node, step: LifecycleStep = LifecycleStep.SLICE_DESIGN
) -> None:
    """Point a dispatch rig's gate reads at a healthy stub ``cf`` for ``slice_node``.

    CF stands one past ``step``'s exit gate, the design is in the checkout, no
    hatch applies. Tick-level routing tests that must advance call this.
    """
    assert slice_node.parent_id is not None and slice_node.cf.index is not None
    initiative = rig.store.get_node(slice_node.parent_id)
    assert initiative is not None and initiative.cf.index is not None
    gates = rig.world.root.parent / "gates"
    gates.mkdir(exist_ok=True)
    checkout = git_checkout(rig.world.root)
    write_design(checkout, DESIGN_PATH)
    knobs = {
        **write_slice_list(
            gates / "plan", initiative.cf.index, {slice_node.cf.index: DESIGN_PATH}
        ),
        **single_status_knobs(
            status_fixture(
                gates / "status.json", CLEAR_FIXTURE[step], slice_node.cf.index
            )
        ),
        **config_knobs(gates, {CF_KEY_REVIEW_GATE_EFFECTIVE_DATE: ""}),
    }
    rig.tick_rig.gate_run = rig.world.run(knobs)


RIG_GITIGNORE = "*\n!.gitignore\n!README.md\n"


def rig_checkout(path: Path) -> Path:
    """A clean git repository on ``main`` that stays clean as a rig writes into it.

    Runs write review files and logs into a checkout; Squadron commits its own output,
    so a real checkout would stay clean. Ignoring everything but ``README.md`` keeps
    these ones clean too. A test that wants a dirty tree edits ``README.md``.
    """
    repo = make_repo(path)
    commit_file(repo, ".gitignore", RIG_GITIGNORE, "ignore rig output")
    return repo


def git_checkout(checkout: Path, branch: str = "main") -> Path:
    """Make ``checkout`` a real git repository on ``branch`` with one commit.

    A directory that already is one (a dispatch rig's checkout) is left as it is.
    """
    if (checkout / ".git").exists():
        return checkout
    return make_repo(checkout, branch)


def write_design(
    checkout: Path, design_path: str, frontmatter: Mapping[str, str] | None = None
) -> Path:
    """Write a slice design with the given frontmatter at ``design_path``."""
    path = checkout / design_path
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = {
        "docType": "slice-design",
        "dateCreated": "20261026",
        **(frontmatter or {}),
    }
    lines = "".join(f"{key}: {value}\n" for key, value in fields.items())
    path.write_text(f"---\n{lines}---\n\n# Slice Design\n", encoding="utf-8")
    return path


def write_slice_list(
    plan_dir: Path, initiative_index: int, design_files: Mapping[int, str]
) -> dict[str, str]:
    """The stub's ``cf list slices`` answer: each slice's index to its design file.

    Returns the knob that points the stub at the plan directory.
    """
    plan_dir.mkdir(parents=True, exist_ok=True)
    entries = [
        {
            "index": index,
            "name": f"slice {index}",
            "isChecked": False,
            "designFile": design_file,
        }
        for index, design_file in design_files.items()
    ]
    (plan_dir / f"slices-{initiative_index}.json").write_text(
        json.dumps({"entries": entries}), encoding="utf-8"
    )
    return {PLAN_DIR_ENV: str(plan_dir)}


def status_fixture(destination: Path, captured: str, slice_index: int) -> Path:
    """A captured status fixture restated for ``slice_index``, saved there.

    Only ``activeSlice.index`` changes; CF answers about the slice its pointer holds.
    """
    document = json.loads((STATUS_FIXTURES / f"{captured}.json").read_text("utf-8"))
    document["activeSlice"]["index"] = slice_index
    destination.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    return destination


def status_knobs(
    tmp_path: Path, fixtures_by_checkout: Mapping[Path, Path]
) -> dict[str, str]:
    """The knob that makes each checkout's ``cf status`` answer its own fixture."""
    return {
        STATUS_MAP_ENV: str(
            write_status_map(tmp_path / "status-map.json", fixtures_by_checkout)
        )
    }


def single_status_knobs(fixture: Path) -> dict[str, str]:
    """The knob that makes every ``cf status`` answer one fixture."""
    return {STATUS_FIXTURE_ENV: str(fixture)}


def config_knobs(tmp_path: Path, values: Mapping[str, str]) -> dict[str, str]:
    """The knob that sets what ``cf config get`` answers for each key."""
    return {CONFIG_ENV: str(write_config_values(tmp_path / "config.json", values))}
