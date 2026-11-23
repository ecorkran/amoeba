"""``gather_runs``: the client part's read of the machine's runs (slice 261, 12.1)."""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Sequence
from pathlib import Path

import pytest
from fake_sq import RUN_FILE, SQUADRON_FIXTURES
from store.question_support import NOW

from amoeba.operations import run_gather
from amoeba.operations.calls_log import append_call, result_entry
from amoeba.operations.run_gather import gather_runs, scratch_roots
from amoeba.operations.runs_document import PAUSED_STATUS, LookupKind, RunsDocument
from amoeba.upstream.squadron.run_list import PAUSED_STATUS as LIST_PAUSED_STATUS
from amoeba.upstream.squadron.run_list import ListedRun, RunListProblem
from operations.status_support import CfAnswer, FakeCf, in_directory, recorded_run

PAUSED = "demo-pause-1"
RUNNING = "run-20261111-p6-fe470d63"
FAILED = "run-20261110-p6-9ea18232"
COMPLETED = "run-20261106-tasks-plan-711d0fe6"
CF_ID = "cf-forge"


class _Rig:
    def __init__(self, tmp_path: Path) -> None:
        self.runs_dir = tmp_path / "runs"
        self.calls_dir = tmp_path / "calls"
        self.scratch = tmp_path / "answering"
        self.runs_dir.mkdir()
        self.scratch.mkdir()
        self.time = 0.0

    def clock(self) -> float:
        return self.time

    def gather(
        self, listing: list[ListedRun] | RunListProblem, cf: object
    ) -> RunsDocument:
        return gather_runs(
            list_runs=lambda: listing,
            run=cf,  # pyright: ignore[reportArgumentType]
            runs_dir=self.runs_dir,
            calls_dir=self.calls_dir,
            scratch_dirs=(self.scratch,),
            clock=self.clock,
        )

    def write_run_file(self, run_id: str) -> None:
        shutil.copy(SQUADRON_FIXTURES / RUN_FILE, self.runs_dir / f"{run_id}.json")


@pytest.fixture
def rig(tmp_path: Path) -> _Rig:
    return _Rig(tmp_path)


def _directories(tmp_path: Path, *names: str) -> list[Path]:
    paths = [tmp_path / name for name in names]
    for path in paths:
        path.mkdir()
    return paths


def test_each_kind_of_run_and_lookup_is_in_the_document(
    tmp_path: Path, rig: _Rig
) -> None:
    forge, other = _directories(tmp_path, "forge", "other")
    rig.write_run_file(PAUSED)
    append_call(
        rig.calls_dir,
        result_entry(PAUSED, forge, "skipped", "settled", None, NOW),
        NOW,
    )
    listing = [
        in_directory(recorded_run(PAUSED), forge),
        in_directory(recorded_run(RUNNING), other),
        in_directory(recorded_run(FAILED), None),
        in_directory(
            recorded_run("run-20261105-effort-compact-acbbe8e8"), tmp_path / "gone"
        ),
        recorded_run(COMPLETED),
    ]
    cf = FakeCf({forge: CF_ID, other: CfAnswer.NOT_A_PROJECT})

    document = rig.gather(listing, cf)

    by_id = {run.run_id: run for run in document.open_runs}
    paused = by_id[PAUSED]
    assert (paused.lookup.kind, paused.lookup.project_id) == (
        LookupKind.PROJECT,
        CF_ID,
    )
    assert paused.run_file is not None
    assert paused.run_file.execution_mode in {"sdk", "prompt-only"}
    assert paused.last_call is not None
    assert (paused.last_call.outcome, paused.last_call.reason) == ("skipped", "settled")
    assert by_id[RUNNING].lookup.kind is LookupKind.NOT_A_PROJECT
    assert by_id[FAILED].lookup.kind is LookupKind.NO_DIRECTORY
    gone = by_id["run-20261105-effort-compact-acbbe8e8"]
    assert gone.lookup.kind is LookupKind.DIRECTORY_MISSING
    assert [(run.run_id, run.status) for run in document.completed_runs] == [
        (COMPLETED, "completed")
    ]
    assert document.open_runs[0].run_id == PAUSED, "paused runs come first"
    assert sorted(cf.calls) == sorted([forge, other])


def test_a_directory_is_looked_up_once_for_all_its_runs(
    tmp_path: Path, rig: _Rig
) -> None:
    (forge,) = _directories(tmp_path, "forge")
    rig.write_run_file(PAUSED)
    listing = [
        in_directory(recorded_run(PAUSED), forge),
        in_directory(recorded_run(RUNNING), forge),
    ]
    cf = FakeCf({forge: CF_ID})

    rig.gather(listing, cf)

    assert cf.calls == [forge]


def test_a_failed_lookup_and_a_missing_run_file_are_values(
    tmp_path: Path, rig: _Rig
) -> None:
    (forge,) = _directories(tmp_path, "forge")
    listing = [in_directory(recorded_run(PAUSED), forge)]

    document = rig.gather(listing, FakeCf({forge: CfAnswer.FAILS}))

    (paused,) = document.open_runs
    assert paused.lookup.kind is LookupKind.FAILED
    assert paused.lookup.detail
    assert paused.run_file is None
    assert paused.run_file_problem is not None
    assert "does not exist" in paused.run_file_problem


def test_an_answering_scratch_run_is_left_out_with_no_cf_call(
    tmp_path: Path, rig: _Rig
) -> None:
    scratch_run = rig.scratch / "answering-1"
    scratch_run.mkdir()
    listing = [in_directory(recorded_run(PAUSED), scratch_run)]
    cf = FakeCf({})

    document = rig.gather(listing, cf)

    assert document.open_runs == ()
    assert cf.calls == []


def test_a_listing_problem_is_the_whole_document(rig: _Rig) -> None:
    document = rig.gather(RunListProblem("`sq` was not found on PATH"), FakeCf({}))

    assert document.listing_problem == "`sq` was not found on PATH"
    assert (document.open_runs, document.completed_runs) == ((), ())


def test_calls_log_problems_are_listed_once(tmp_path: Path, rig: _Rig) -> None:
    (forge,) = _directories(tmp_path, "forge")
    rig.write_run_file(PAUSED)
    rig.calls_dir.mkdir()
    (rig.calls_dir / "2026-11-22.jsonl").write_text("not json\n", encoding="utf-8")

    document = rig.gather(
        [in_directory(recorded_run(PAUSED), forge)], FakeCf({forge: CF_ID})
    )

    assert len(document.call_problems) == 1


def test_once_the_gather_time_is_spent_the_remaining_directories_say_so(
    tmp_path: Path, rig: _Rig, monkeypatch: pytest.MonkeyPatch
) -> None:
    first, second, third = _directories(tmp_path, "one", "two", "three")
    for run_id in (PAUSED, "demo-push-3", "amoeba-20261110T150234Z-8bf24f09cfbb"):
        rig.write_run_file(run_id)
    monkeypatch.setattr(run_gather, "RUNS_GATHER_SECONDS", 15.0)
    answers = FakeCf({first: CF_ID, second: CF_ID, third: CF_ID})

    def slow(argv: Sequence[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        rig.time += 10.0  # each `cf get` takes ten seconds
        return answers(argv, **kwargs)

    listing = [
        in_directory(recorded_run(PAUSED), first),
        in_directory(recorded_run("demo-push-3"), second),
        in_directory(recorded_run("amoeba-20261110T150234Z-8bf24f09cfbb"), third),
    ]

    document = rig.gather(listing, slow)

    kinds = [run.lookup.kind for run in document.open_runs]
    assert kinds == [LookupKind.PROJECT, LookupKind.PROJECT, LookupKind.FAILED]
    ran_out = document.open_runs[2].lookup.detail
    assert ran_out is not None and "ran out" in ran_out
    assert answers.calls == [first, second]


def test_scratch_roots_name_the_legacy_directory_only_when_there_is_a_legacy_home(
    tmp_path: Path,
) -> None:
    assert scratch_roots(tmp_path / "a", None) == (tmp_path / "a",)
    assert scratch_roots(tmp_path / "a", tmp_path / "b") == (
        tmp_path / "a",
        tmp_path / "b" / "answering",
    )


def test_a_run_under_the_legacy_answering_directory_is_left_out_with_no_cf_call(
    tmp_path: Path, rig: _Rig
) -> None:
    legacy = tmp_path / "legacy" / "answering" / "amoeba-20261111T000000Z-bbbbbbbbbbbb"
    legacy.mkdir(parents=True)
    cf = FakeCf({})

    document = gather_runs(
        list_runs=lambda: [in_directory(recorded_run(PAUSED), legacy)],
        run=cf,  # pyright: ignore[reportArgumentType]
        runs_dir=rig.runs_dir,
        calls_dir=rig.calls_dir,
        scratch_dirs=scratch_roots(rig.scratch, tmp_path / "legacy"),
        clock=rig.clock,
    )

    assert document.open_runs == ()
    assert cf.calls == []


def test_a_missing_directory_is_recorded_with_no_cf_call(
    tmp_path: Path, rig: _Rig
) -> None:
    cf = FakeCf({})

    document = rig.gather(
        [in_directory(recorded_run(RUNNING), tmp_path / "removed-worktree")], cf
    )

    assert document.open_runs[0].lookup.kind is LookupKind.DIRECTORY_MISSING
    assert cf.calls == []


def test_the_documents_status_names_are_squadrons() -> None:
    """``runs_document`` may not import ``upstream``, so it names the paused status
    itself; this pins it to the listing reader's."""
    assert PAUSED_STATUS == LIST_PAUSED_STATUS
