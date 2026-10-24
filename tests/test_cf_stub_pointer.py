"""The stub ``cf``'s pointer commands: ``set slice`` and ``get --json`` by cwd (125)."""

from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Mapping
from functools import partial
from pathlib import Path

import pytest
from cf_stub import (
    ARTIFACT_NOT_FOUND,
    GET_MODE_ENV,
    GET_QUIRK_ENV,
    QUIRK_PROJECT_PATH,
    QUIRK_WORKTREE_ID,
    SET_MODE_ENV,
    STATE_ENV,
    GetQuirk,
    PointerMode,
    read_cf_state,
    write_cf_state,
    write_cf_stub,
)

from amoeba.process.observers.cf_readback import (
    RESULT_FILE_SLICE,
    RESULT_PROJECT_PATH,
    RESULT_WORKTREE_ID,
    read_back_cf_write,
)
from amoeba.process.recovery import Adopt, NotApplied, Observation, Unknown
from amoeba.store import (
    PARAM_CHECKOUT,
    PARAM_EXPECTED_SLICE_INDEX,
    CommandKind,
    JournalEntry,
)

CF_ID = "project_1_abc"
STEM_125 = "125-slice.run-dispatch-and-outcome-ingestion"
STEM_225 = "225-slice.second-worktree-work"


class Rig:
    """A stub ``cf``, a state file and two worktrees under a temporary directory."""

    def __init__(self, tmp_path: Path) -> None:
        self.root = tmp_path / "main"
        self.second = tmp_path / "second"
        self.outside = tmp_path / "outside"
        for directory in (self.root, self.second, self.outside):
            directory.mkdir()
        self.state_path = tmp_path / "cf-state.json"
        self.bin_dir = write_cf_stub(tmp_path / "bin")
        write_cf_state(
            self.state_path,
            cf_project_id=CF_ID,
            project_path=self.root,
            worktrees=[
                self._worktree("wt_a", self.root, 100, 199),
                self._worktree("wt_b", self.second, 200, 299),
            ],
            slices={125: STEM_125, 225: STEM_225},
            file_slice="000-slice.project-level",
        )

    @staticmethod
    def _worktree(
        worktree_id: str, path: Path, low: int, high: int
    ) -> dict[str, object]:
        return {
            "id": worktree_id,
            "name": worktree_id,
            "worktreePath": str(path),
            "indexRange": [low, high],
            "activeSlice": f"{low}-slice.before",
        }

    def env(self, knobs: Mapping[str, str] | None = None) -> dict[str, str]:
        return {
            **os.environ,
            "PATH": f"{self.bin_dir}{os.pathsep}{os.environ['PATH']}",
            STATE_ENV: str(self.state_path),
            **(knobs or {}),
        }

    def cf(
        self,
        *arguments: str,
        cwd: Path,
        timeout: float = 30,
        knobs: Mapping[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["cf", *arguments],
            cwd=cwd,
            env=self.env(knobs),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )

    def set_slice(
        self, index: int, cwd: Path, knobs: Mapping[str, str] | None = None
    ) -> subprocess.CompletedProcess[str]:
        return self.cf("set", "-p", CF_ID, "slice", str(index), cwd=cwd, knobs=knobs)

    def get(
        self, cwd: Path, knobs: Mapping[str, str] | None = None
    ) -> dict[str, object]:
        result = self.cf("get", "--json", "-p", CF_ID, cwd=cwd, knobs=knobs)
        assert result.returncode == 0, result.stderr
        document: dict[str, object] = json.loads(result.stdout)
        return document

    def state(self) -> dict[str, object]:
        return read_cf_state(self.state_path)

    def worktree(self, worktree_id: str) -> dict[str, object]:
        [found] = [w for w in self.state()["worktrees"] if w["id"] == worktree_id]  # type: ignore[index, union-attr]
        return found  # type: ignore[no-any-return]


@pytest.fixture
def rig(tmp_path: Path) -> Rig:
    return Rig(tmp_path)


def test_a_write_from_each_worktree_lands_in_its_own(rig: Rig) -> None:
    assert rig.set_slice(125, rig.root).returncode == 0
    assert rig.set_slice(225, rig.second).returncode == 0

    assert rig.worktree("wt_a")["activeSlice"] == STEM_125
    assert rig.worktree("wt_b")["activeSlice"] == STEM_225
    assert rig.state()["fileSlice"] == "000-slice.project-level"


def test_a_write_from_a_subdirectory_lands_in_the_longest_prefix(
    rig: Rig, tmp_path: Path
) -> None:
    nested = rig.second / "deep" / "er"
    nested.mkdir(parents=True)

    assert rig.set_slice(225, nested).returncode == 0

    assert rig.worktree("wt_b")["activeSlice"] == STEM_225


def test_a_write_from_outside_every_worktree_lands_at_project_level(rig: Rig) -> None:
    assert rig.set_slice(125, rig.outside).returncode == 0

    assert rig.state()["fileSlice"] == STEM_125
    assert rig.worktree("wt_a")["activeSlice"] == "100-slice.before"


def test_a_write_bumps_updated_at_and_an_unchanged_value_writes_nothing(
    rig: Rig,
) -> None:
    before = rig.state()["updatedAt"]
    rig.set_slice(125, rig.root)
    bumped = rig.state()["updatedAt"]
    first_bytes = rig.state_path.read_bytes()

    again = rig.set_slice(125, rig.root)

    assert again.returncode == 0
    assert bumped != before
    assert rig.state_path.read_bytes() == first_bytes


def test_an_index_with_no_slice_plan_entry_fails_and_changes_nothing(rig: Rig) -> None:
    before = rig.state_path.read_bytes()

    result = rig.set_slice(999, rig.root)

    assert result.returncode == 1
    assert ARTIFACT_NOT_FOUND in result.stderr
    assert rig.state_path.read_bytes() == before


def test_set_can_be_made_to_fail(rig: Rig) -> None:
    before = rig.state_path.read_bytes()

    result = rig.set_slice(125, rig.root, knobs={SET_MODE_ENV: PointerMode.FAIL.value})

    assert result.returncode == 1
    assert rig.state_path.read_bytes() == before


def test_get_in_a_worktree_reports_its_path_slice_and_worktree(rig: Rig) -> None:
    rig.set_slice(225, rig.second)

    document = rig.get(rig.second)

    assert document["projectPath"] == str(rig.second)
    assert document["fileSlice"] == STEM_225
    worktree = document["worktree"]
    assert isinstance(worktree, dict) and worktree["id"] == "wt_b"  # pyright: ignore[reportUnknownMemberType]
    assert "slices" not in document and "worktrees" not in document


def test_get_outside_every_worktree_reports_the_project_level(rig: Rig) -> None:
    document = rig.get(rig.outside)

    assert document["projectPath"] == str(rig.root)
    assert document["fileSlice"] == "000-slice.project-level"
    assert "worktree" not in document


def test_get_can_be_made_to_fail(rig: Rig) -> None:
    result = rig.cf(
        "get",
        "--json",
        "-p",
        CF_ID,
        cwd=rig.root,
        knobs={GET_MODE_ENV: PointerMode.FAIL.value},
    )

    assert result.returncode == 1


def test_get_can_be_made_to_hang(rig: Rig) -> None:
    with pytest.raises(subprocess.TimeoutExpired):
        rig.cf(
            "get",
            "--json",
            "-p",
            CF_ID,
            cwd=rig.root,
            timeout=0.5,
            knobs={GET_MODE_ENV: PointerMode.SLEEP.value},
        )


def test_get_can_omit_file_slice(rig: Rig) -> None:
    document = rig.get(rig.root, knobs={GET_QUIRK_ENV: GetQuirk.OMIT_FILE_SLICE.value})

    assert "fileSlice" not in document


def test_get_can_report_another_project_path(rig: Rig) -> None:
    document = rig.get(
        rig.root, knobs={GET_QUIRK_ENV: GetQuirk.OTHER_PROJECT_PATH.value}
    )

    assert document["projectPath"] == QUIRK_PROJECT_PATH


def test_get_can_report_another_worktree_id(rig: Rig) -> None:
    document = rig.get(
        rig.root, knobs={GET_QUIRK_ENV: GetQuirk.OTHER_WORKTREE_ID.value}
    )

    worktree = document["worktree"]
    assert isinstance(worktree, dict) and worktree["id"] == QUIRK_WORKTREE_ID  # pyright: ignore[reportUnknownMemberType]


# -- the read-back observer parses what the stub prints ----------------------------


def _entry(rig: Rig, checkout: Path, index: int) -> JournalEntry:
    return JournalEntry(
        id="entry-1",
        project_id="demo",
        node_id="node-1",
        kind=CommandKind.CF_WRITE,
        parameters={
            "project": CF_ID,
            "expected": {},
            PARAM_CHECKOUT: str(checkout),
            PARAM_EXPECTED_SLICE_INDEX: index,
        },
    )


def _read_back(
    rig: Rig, entry: JournalEntry, knobs: Mapping[str, str] | None = None
) -> Observation:
    run = partial(subprocess.run, env=rig.env(knobs))
    return read_back_cf_write(entry, run, 30.0)


def test_the_observer_adopts_what_the_stub_wrote(rig: Rig) -> None:
    rig.set_slice(125, rig.root)

    observation = _read_back(rig, _entry(rig, rig.root, 125))

    assert isinstance(observation, Adopt)
    assert observation.result[RESULT_FILE_SLICE] == STEM_125
    assert observation.result[RESULT_WORKTREE_ID] == "wt_a"
    assert observation.result[RESULT_PROJECT_PATH] == str(rig.root)


def test_the_observer_sees_another_index_as_not_applied(rig: Rig) -> None:
    rig.set_slice(125, rig.root)

    assert isinstance(_read_back(rig, _entry(rig, rig.root, 126)), NotApplied)


def test_the_observer_cannot_judge_a_record_with_no_file_slice(rig: Rig) -> None:
    rig.set_slice(125, rig.root)
    quirk = {GET_QUIRK_ENV: GetQuirk.OMIT_FILE_SLICE.value}

    assert isinstance(_read_back(rig, _entry(rig, rig.root, 125), quirk), Unknown)
