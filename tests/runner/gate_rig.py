"""Rig helpers for the gate tests: a real git checkout, a design, a status fixture.

They build the pieces the stub ``cf`` reads (``tests/cf_stub_gates.py``) and return the
environment knobs a ``CfWorld.run`` / ``DispatchRig.use_world`` call takes.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

from cf_stub import PLAN_DIR_ENV
from cf_stub_gates import (
    CONFIG_ENV,
    STATUS_FIXTURE_ENV,
    STATUS_MAP_ENV,
    write_config_values,
    write_status_map,
)

from amoeba.runner.gates.outcome import OutcomeObservation, unobservable
from amoeba.store import JournalEntry
from runner.git_repo import make_repo

STATUS_FIXTURES = Path(__file__).parents[1] / "fixtures" / "cf" / "status"


def failed_reads(entry: JournalEntry) -> OutcomeObservation:
    """An observation in which every read failed, for tests that ingest directly.

    Ingesting a ``completed`` run needs an observation; these tests do not care what
    CF said, only that the run is recorded.
    """
    return unobservable(entry, entry.node_id, "test: nothing was read", "amoeba-test")


def git_checkout(checkout: Path, branch: str = "main") -> Path:
    """Make ``checkout`` a real git repository on ``branch`` with one commit."""
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
