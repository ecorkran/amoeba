"""``place_runs``: every placement rule of D4, on the ``runs`` document
(slice 224, 3.5; 261, D11)."""

from __future__ import annotations

from pathlib import Path

from store.question_support import NOW

from amoeba.operations.runs_document import LookupKind, OpenRun, RunLookup
from amoeba.operations.status_models import UnplacedReason
from amoeba.operations.status_placement import Placement, place_runs
from amoeba.store.models import Member, MemberSettings
from amoeba.store.vocabulary import RulesFrom
from operations.runs_doc_support import failed, not_a_project, open_run, project
from operations.status_support import in_directory, recorded_run

MEMBER_ID = "project-in-scope"
MEMBER = Member(
    "demo",
    MemberSettings(MEMBER_ID, (), (), (), RulesFrom.NAMED),
    NOW,
    NOW,
    None,
    MEMBER_ID,
    None,
)
PAUSED = "demo-pause-1"
PAUSED_OTHER_KIND = "run-20261004-p6-8bc5e634"
RUNNING = "run-20261111-p6-fe470d63"
FAILED = "run-20261105-effort-compact-acbbe8e8"


DIRECTORY = Path("/work/forge")
MISSING = RunLookup(kind=LookupKind.DIRECTORY_MISSING)


def _place(*runs: OpenRun) -> Placement:
    return place_runs(runs, {MEMBER_ID: MEMBER})


def _in(run_id: str, lookup: RunLookup) -> OpenRun:
    return open_run(in_directory(recorded_run(run_id), DIRECTORY), lookup)


def test_a_none_directory_is_unplaced_for_a_paused_run_with_its_kind() -> None:
    result = _place(open_run(in_directory(recorded_run(PAUSED), None)))

    (entry,) = result.unplaced
    assert entry.run_id == PAUSED
    assert entry.reason is UnplacedReason.NO_DIRECTORY
    assert entry.checkpoint_kind == "agent_question"
    assert entry.status == "paused"
    assert result.placed == ()


def test_running_and_failed_runs_with_null_directories_give_no_entry() -> None:
    result = _place(
        open_run(in_directory(recorded_run(RUNNING), None)),
        open_run(in_directory(recorded_run(FAILED), None)),
    )

    assert result == Placement((), ())


def test_the_recordings_null_directory_paused_runs_keep_their_kinds() -> None:
    result = _place(
        open_run(recorded_run("run-20261105-p6-7dc230a3")),
        open_run(recorded_run(PAUSED_OTHER_KIND)),
    )

    assert [entry.checkpoint_kind for entry in result.unplaced] == [
        "awaits_human",
        "interactive_checkpoint",
    ]


def test_a_missing_directory_is_unplaced() -> None:
    result = _place(_in(PAUSED, MISSING))

    assert [entry.reason for entry in result.unplaced] == [
        UnplacedReason.DIRECTORY_MISSING
    ]


def test_a_missing_directory_of_a_running_run_is_not_listed() -> None:
    assert _place(_in(RUNNING, MISSING)) == Placement((), ())


def test_a_directory_in_no_project_or_a_project_outside_the_scope_is_dropped() -> None:
    result = _place(
        _in(PAUSED, not_a_project()),
        _in(RUNNING, project("another-program")),
    )

    assert result == Placement((), ())


def test_a_lookup_failure_is_unplaced_with_the_error_and_leaves_the_rest_placed() -> (
    None
):
    result = _place(
        _in(PAUSED, failed("`cf get --json` timed out after 30.0s")),
        _in("demo-push-3", project(MEMBER_ID)),
    )

    (entry,) = result.unplaced
    assert entry.reason is UnplacedReason.LOOKUP_FAILED
    assert entry.detail == "`cf get --json` timed out after 30.0s"
    assert [placed.run.run_id for placed in result.placed] == ["demo-push-3"]


def test_a_gather_time_that_ran_out_leaves_a_paused_run_unplaced() -> None:
    result = _place(_in(PAUSED, failed("the 60 s allowed ran out before this one")))

    (entry,) = result.unplaced
    assert entry.reason is UnplacedReason.LOOKUP_FAILED
    assert result.placed == ()


def test_a_failed_lookup_of_a_running_run_is_not_listed() -> None:
    assert _place(_in(RUNNING, failed("down"))) == Placement((), ())


def test_runs_of_two_worktrees_of_one_repo_land_on_one_member() -> None:
    result = _place(
        _in(PAUSED, project(MEMBER_ID)),
        _in("demo-push-3", project(MEMBER_ID)),
        _in(RUNNING, project(MEMBER_ID)),
    )

    assert [placed.member for placed in result.placed] == [MEMBER] * 3


def test_a_run_is_placed_by_the_checkout_id_not_by_the_member_id() -> None:
    other = Member(
        "demo",
        MemberSettings("member-id-b", (), (), (), RulesFrom.NAMED),
        NOW,
        NOW,
        None,
        "b",
        None,
    )

    result = place_runs([_in(PAUSED, project("cf-of-b"))], {"cf-of-b": other})

    assert [placed.member for placed in result.placed] == [other]
    assert place_runs([_in(PAUSED, project("member-id-b"))], {"cf-of-b": other}) == (
        Placement((), ())
    )


def test_unplaced_runs_are_not_filtered_by_program() -> None:
    result = place_runs([open_run(recorded_run("run-20261105-p6-7dc230a3"))], {})

    assert len(result.unplaced) == 1
