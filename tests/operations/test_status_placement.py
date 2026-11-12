"""``place_runs``: every placement rule of D4 (slice 224, 3.5)."""

from __future__ import annotations

from pathlib import Path

import pytest
from store.question_support import NOW

from amoeba.operations.status_models import UnplacedReason
from amoeba.operations.status_placement import Placement, place_runs, scratch_roots
from amoeba.store.models import Member, MemberSettings
from amoeba.upstream.context_forge.cli_call import CfCallFailed
from amoeba.upstream.context_forge.project_of import CFProject, CFProjectNotFound
from amoeba.upstream.squadron.run_list import ListedRun
from operations.status_support import in_directory, recorded_run

MEMBER_ID = "project-in-scope"
MEMBER = Member(
    "demo",
    MemberSettings(MEMBER_ID, (), (), ()),
    NOW,
    NOW,
    None,
)
PAUSED = "demo-pause-1"
PAUSED_OTHER_KIND = "run-20261004-p6-8bc5e634"
RUNNING = "run-20261111-p6-fe470d63"
FAILED = "run-20261105-effort-compact-acbbe8e8"


class _ProjectOf:
    """A ``project_of`` stand-in: an answer per directory, and the calls made."""

    def __init__(
        self, answers: dict[Path, CFProject | CFProjectNotFound | CfCallFailed]
    ):
        self.answers = answers
        self.calls: list[Path] = []

    def __call__(self, directory: Path) -> CFProject | CFProjectNotFound | CfCallFailed:
        self.calls.append(directory)
        return self.answers[directory]


def _project(project_id: str = MEMBER_ID) -> CFProject:
    return CFProject(id=project_id, name="n", project_path="/p")


@pytest.fixture
def scratch(tmp_path: Path) -> Path:
    path = tmp_path / "answering"
    path.mkdir()
    return path


def _place(runs: list[ListedRun], project_of: _ProjectOf, scratch: Path) -> Placement:
    return place_runs(runs, {MEMBER_ID: MEMBER}, (scratch,), project_of)


def test_a_none_directory_is_unplaced_for_a_paused_run_with_its_kind(
    scratch: Path,
) -> None:
    runs = [in_directory(recorded_run(PAUSED), None)]
    project_of = _ProjectOf({})

    result = _place(runs, project_of, scratch)

    (entry,) = result.unplaced
    assert entry.run_id == PAUSED
    assert entry.reason is UnplacedReason.NO_DIRECTORY
    assert entry.checkpoint_kind == "agent_question"
    assert entry.status == "paused"
    assert result.placed == ()
    assert project_of.calls == []


def test_running_and_failed_runs_with_null_directories_give_no_entry(
    scratch: Path,
) -> None:
    runs = [
        in_directory(recorded_run(RUNNING), None),
        in_directory(recorded_run(FAILED), None),
    ]

    result = _place(runs, _ProjectOf({}), scratch)

    assert result == Placement((), ())


def test_the_recordings_null_directory_paused_runs_keep_their_kinds(
    scratch: Path,
) -> None:
    runs = [recorded_run("run-20261105-p6-7dc230a3"), recorded_run(PAUSED_OTHER_KIND)]

    result = _place(runs, _ProjectOf({}), scratch)

    assert [entry.checkpoint_kind for entry in result.unplaced] == [
        "awaits_human",
        "interactive_checkpoint",
    ]


def test_a_missing_directory_is_unplaced_before_any_cf_call(
    tmp_path: Path, scratch: Path
) -> None:
    runs = [in_directory(recorded_run(PAUSED), tmp_path / "removed-worktree")]
    project_of = _ProjectOf({})

    result = _place(runs, project_of, scratch)

    assert [entry.reason for entry in result.unplaced] == [
        UnplacedReason.DIRECTORY_MISSING
    ]
    assert project_of.calls == []


def test_a_missing_directory_of_a_running_run_is_not_listed(
    tmp_path: Path, scratch: Path
) -> None:
    runs = [in_directory(recorded_run(RUNNING), tmp_path / "removed")]

    assert _place(runs, _ProjectOf({}), scratch) == Placement((), ())


def test_the_scratch_directory_is_dropped_with_no_cf_call(scratch: Path) -> None:
    run_directory = scratch / "amoeba-20261111T000000Z-aaaaaaaaaaaa"
    run_directory.mkdir()
    runs = [in_directory(recorded_run(PAUSED), run_directory)]
    project_of = _ProjectOf({})

    result = _place(runs, project_of, scratch)

    assert result == Placement((), ())
    assert project_of.calls == []


def test_a_run_under_the_legacy_answering_directory_is_skipped_with_no_cf_call(
    tmp_path: Path, scratch: Path
) -> None:
    legacy_home = tmp_path / "legacy"
    run_directory = legacy_home / "answering" / "amoeba-20261111T000000Z-bbbbbbbbbbbb"
    run_directory.mkdir(parents=True)
    runs = [in_directory(recorded_run(PAUSED), run_directory)]
    project_of = _ProjectOf({})

    result = place_runs(
        runs,
        {MEMBER_ID: MEMBER},
        scratch_roots(scratch, legacy_home),
        project_of,
    )

    assert result == Placement((), ())
    assert project_of.calls == []


def test_scratch_roots_name_the_legacy_directory_only_when_there_is_a_legacy_home(
    tmp_path: Path,
) -> None:
    assert scratch_roots(tmp_path / "a", None) == (tmp_path / "a",)
    assert scratch_roots(tmp_path / "a", tmp_path / "b") == (
        tmp_path / "a",
        tmp_path / "b" / "answering",
    )


def test_a_directory_in_no_project_or_a_project_outside_the_scope_is_dropped(
    tmp_path: Path, scratch: Path
) -> None:
    outside = tmp_path / "outside"
    elsewhere = tmp_path / "elsewhere"
    outside.mkdir()
    elsewhere.mkdir()
    runs = [
        in_directory(recorded_run(PAUSED), outside),
        in_directory(recorded_run(RUNNING), elsewhere),
    ]
    project_of = _ProjectOf(
        {outside: CFProjectNotFound("none"), elsewhere: _project("another-program")}
    )

    assert _place(runs, project_of, scratch) == Placement((), ())


def test_a_lookup_failure_is_unplaced_with_the_error_and_leaves_the_rest_placed(
    tmp_path: Path, scratch: Path
) -> None:
    broken = tmp_path / "broken"
    good = tmp_path / "good"
    broken.mkdir()
    good.mkdir()
    runs = [
        in_directory(recorded_run(PAUSED), broken),
        in_directory(recorded_run("demo-push-3"), good),
    ]
    project_of = _ProjectOf(
        {
            broken: CfCallFailed("`cf get --json` timed out after 30.0s"),
            good: _project(),
        }
    )

    result = _place(runs, project_of, scratch)

    (entry,) = result.unplaced
    assert entry.reason is UnplacedReason.LOOKUP_FAILED
    assert entry.detail == "`cf get --json` timed out after 30.0s"
    assert [placed.run.run_id for placed in result.placed] == ["demo-push-3"]


def test_a_failed_lookup_of_a_running_run_is_not_listed(
    tmp_path: Path, scratch: Path
) -> None:
    broken = tmp_path / "broken"
    broken.mkdir()
    runs = [in_directory(recorded_run(RUNNING), broken)]

    result = _place(runs, _ProjectOf({broken: CfCallFailed("down")}), scratch)

    assert result == Placement((), ())


def test_two_worktrees_of_one_repo_land_on_one_member_one_call_per_directory(
    tmp_path: Path, scratch: Path
) -> None:
    first = tmp_path / "worktree-a"
    second = tmp_path / "worktree-b"
    first.mkdir()
    second.mkdir()
    runs = [
        in_directory(recorded_run(PAUSED), first),
        in_directory(recorded_run("demo-push-3"), first),
        in_directory(recorded_run(RUNNING), second),
    ]
    project_of = _ProjectOf({first: _project(), second: _project()})

    result = _place(runs, project_of, scratch)

    assert [placed.member for placed in result.placed] == [MEMBER] * 3
    assert project_of.calls == [first, second]


def test_unplaced_runs_are_not_filtered_by_program(scratch: Path) -> None:
    runs = [recorded_run("run-20261105-p6-7dc230a3")]

    result = place_runs(runs, {}, (scratch,), _ProjectOf({}))

    assert len(result.unplaced) == 1
