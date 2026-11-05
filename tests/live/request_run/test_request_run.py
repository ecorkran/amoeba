"""Live runs of the slice-writing pipeline: first request, next request, met need.

Each case is one real ``sq run`` in a scratch provider repo, with a real model and
real spend under the cost cap. A wrong outcome fails the test; nothing is retried.
The every-run guarantees are asserted in ``RequestHarness.run`` before a case sees
its result. Cases 1 and 2 share one repo: case 2 runs in the repo case 1 left.
"""

from __future__ import annotations

from typing import Any

import pytest

from amoeba.runner.request_run.reply import AlreadyMet, NewSlice
from live.request_run.harness import RequestHarness, RequestRun
from live.request_run.scratch_repo import (
    EXISTING_INITIATIVE_INDEX,
    INITIATIVE_PLAN_PATH,
    REQUESTS_INDEX,
    SLICE_PLAN_PATH,
    TARGET_BRANCH,
    ScratchRepo,
    cf_json,
    git,
)

FIRST_NEED = (
    "Notes need tags. Add a way to attach one or more text tags to a note and to "
    "list the notes that carry a given tag."
)
SECOND_NEED = (
    "Notes need an export. Add a way to write every note to a single markdown file, "
    "one section per note."
)
MET_NEED = "Provide a function that returns how many notes there are in a list."


def _slice_entries(repo: ScratchRepo, index: int) -> list[dict[str, Any]]:
    listing = cf_json(repo, "list", "slices", str(index), "--json")
    return listing["entries"]


def _initiative_indexes(repo: ScratchRepo) -> list[int]:
    listing = cf_json(repo, "list", "initiatives", "--json", "-a")
    return [entry["index"] for entry in listing]


def _plan_text(repo: ScratchRepo, revision: str, path: str) -> str:
    return git(repo, "show", f"{revision}:{path}")


@pytest.fixture(scope="module")
def first_request(request_harness: RequestHarness) -> RequestRun:
    """Case 1's run, kept so case 2 can run in the repo it left."""
    repo = request_harness.new_repo("provider")
    return request_harness.run(repo, "first", FIRST_NEED)


def test_first_request_creates_initiative_and_one_entry(
    first_request: RequestRun,
) -> None:
    repo = first_request.repo
    assert isinstance(first_request.reply, NewSlice), first_request.reply
    assert REQUESTS_INDEX in _initiative_indexes(repo)
    entries = _slice_entries(repo, REQUESTS_INDEX)
    assert [entry["index"] for entry in entries] == [first_request.reply.index]
    assert len(first_request.new_commits) == 1
    touched = first_request.files_changed_by(first_request.new_commits[0])
    assert INITIATIVE_PLAN_PATH in touched
    assert len(touched) == 2, touched
    (slice_plan,) = touched - {INITIATIVE_PLAN_PATH}
    assert f"/{REQUESTS_INDEX}-slices." in slice_plan, slice_plan


def test_second_request_appends_next_entry_only(
    request_harness: RequestHarness, first_request: RequestRun
) -> None:
    repo = first_request.repo
    assert isinstance(first_request.reply, NewSlice), first_request.reply
    first_index = first_request.reply.index
    (first_commit,) = first_request.new_commits
    (slice_plan,) = first_request.files_changed_by(first_commit) - {
        INITIATIVE_PLAN_PATH
    }
    before_plan = _plan_text(repo, first_commit, slice_plan)
    before_existing = _slice_entries(repo, EXISTING_INITIATIVE_INDEX)

    second = request_harness.run(repo, "second", SECOND_NEED)

    assert isinstance(second.reply, NewSlice), second.reply
    assert second.reply.index == first_index + 1
    entries = _slice_entries(repo, REQUESTS_INDEX)
    assert [entry["index"] for entry in entries] == [first_index, second.reply.index]
    assert len(second.new_commits) == 1
    assert second.files_changed_by(second.new_commits[0]) == {slice_plan}
    after_lines = set(_plan_text(repo, "HEAD", slice_plan).splitlines())
    removed = [
        line
        for line in before_plan.splitlines()
        if line not in after_lines and not line.startswith("dateUpdated:")
    ]
    assert not removed, f"first entry lines changed: {removed}"
    assert _slice_entries(repo, EXISTING_INITIATIVE_INDEX) == before_existing
    assert git(repo, "show", f"HEAD:{SLICE_PLAN_PATH}") == git(
        repo, "show", f"{first_commit}:{SLICE_PLAN_PATH}"
    )


def test_met_need_replies_already_met_without_moving_head(
    request_harness: RequestHarness,
) -> None:
    repo = request_harness.new_repo("met")
    result = request_harness.run(repo, "met", MET_NEED)
    assert isinstance(result.reply, AlreadyMet), result.reply
    assert result.new_commits == ()
    assert git(repo, "rev-parse", "HEAD") == result.start_commit
    # Exits non-zero (so git() raises) when the named commit is not on the target.
    git(repo, "merge-base", "--is-ancestor", result.reply.commit, TARGET_BRANCH)
