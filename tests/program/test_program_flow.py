"""The program flow end to end without a real design run (slice 227, D7, 6.1).

A provider repo reports; a consumer repo takes ``since`` from the consumer rule block's
own git commands and reads ``changes``. Real git repositories, a replayed ``cf``, the
real operations and store.
"""

from __future__ import annotations

from pathlib import Path

from git_repo import commit_file, git, head_of

from amoeba.operations.changes_models import ChangesOutcome, ChangesResult
from amoeba.operations.reject_codes import RejectCode
from amoeba.operations.report_release_models import ReportOutcome
from amoeba.operations.since import parse_since
from amoeba.store.vocabulary import ConsumedMode
from program.flow_support import (
    FlowRig,
    changes_for,
    commit_design,
    day,
    flow_rig,
    report,
    since_from_block,
)


def _merge_report(provider_commit: str, text: str = "merged") -> dict[str, object]:
    return {"commit": provider_commit, "changed": text, "touched": ["api"]}


def _provider_commit(rig: FlowRig, name: str) -> str:
    return commit_file(rig.provider_repo, name, f"{name}\n", f"add {name}")


def _commits(result: ChangesResult) -> list[str]:
    assert result.outcome is ChangesOutcome.LISTED, result.problems
    return [release.commit for pair in result.pairs for release in pair.releases]


def test_the_window_case_a_report_between_design_and_merge_is_seen(
    tmp_path: Path,
) -> None:
    with flow_rig(tmp_path, ConsumedMode.FROM_SOURCE) as rig:
        commit_design(
            rig.consumer_repo, "100-slice.old.md", author="2026-11-02T09:00:00-05:00"
        )
        design = commit_design(
            rig.consumer_repo, "101-slice.new.md", author="2026-11-10T09:00:00-05:00"
        )
        provider = _provider_commit(rig, "interface.txt")
        # After the consumer's design commit, before its merge.
        report(rig, _merge_report(provider), at=day(11))
        git(rig.consumer_repo, "tag", "design-done", design)

        since = since_from_block(rig.consumer_repo)
        result = changes_for(rig, since, rig.consumer_repo)

        assert parse_since(since) == "2026-11-10T14:00:00+00:00"
        assert _commits(result) == [provider]


def test_the_last_merge_time_would_have_missed_that_report(tmp_path: Path) -> None:
    with flow_rig(tmp_path, ConsumedMode.FROM_SOURCE) as rig:
        commit_design(
            rig.consumer_repo, "101-slice.new.md", author="2026-11-10T09:00:00+00:00"
        )
        provider = _provider_commit(rig, "interface.txt")
        report(rig, _merge_report(provider), at=day(11))
        # The control: the consumer merges its slice after the report. A starting
        # point taken from that merge sees nothing, which the block's command avoids.
        merged = "2026-11-12T09:00:00+00:00"
        git(rig.consumer_repo, "checkout", "-q", "-b", "other")
        commit_file(rig.consumer_repo, "code.txt", "code\n", "implement", date=merged)
        git(rig.consumer_repo, "checkout", "-q", "-")
        git(
            rig.consumer_repo,
            "merge",
            "--no-ff",
            "-q",
            "-m",
            "merge",
            "other",
            env={"GIT_AUTHOR_DATE": merged, "GIT_COMMITTER_DATE": merged},
        )

        assert _commits(changes_for(rig, merged, rig.consumer_repo)) == []
        assert _commits(
            changes_for(rig, since_from_block(rig.consumer_repo), rig.consumer_repo)
        ) == [provider]


def test_the_rebase_case_author_time_survives_a_rebase(tmp_path: Path) -> None:
    with flow_rig(tmp_path, ConsumedMode.FROM_SOURCE) as rig:
        repo = rig.consumer_repo
        git(repo, "checkout", "-q", "-b", "slice")
        commit_design(repo, "101-slice.new.md", author="2026-11-10T09:00:00+00:00")
        provider = _provider_commit(rig, "interface.txt")
        report(rig, _merge_report(provider), at=day(11))
        # The target moves on; the branch is rebased after the report.
        git(repo, "checkout", "-q", "main")
        commit_file(
            repo, "later.txt", "later\n", "later", date="2026-11-13T09:00:00+00:00"
        )
        git(repo, "checkout", "-q", "slice")
        rebased = "2026-11-14T09:00:00+00:00"
        git(
            repo,
            "rebase",
            "-q",
            "main",
            env={"GIT_COMMITTER_DATE": rebased},
        )

        committer_time = git(repo, "log", "-1", "--format=%cI").stdout.strip()
        since = since_from_block(repo)

        # The control: committer time moved past the report, author time did not.
        assert parse_since(committer_time) == rebased
        assert parse_since(since) == "2026-11-10T09:00:00+00:00"
        assert _commits(changes_for(rig, since, repo)) == [provider]
        assert _commits(changes_for(rig, committer_time, repo)) == []


def test_with_no_previous_design_the_root_commit_time_is_accepted(
    tmp_path: Path,
) -> None:
    with flow_rig(tmp_path, ConsumedMode.FROM_SOURCE) as rig:
        root = git(
            rig.consumer_repo, "log", "--max-parents=0", "--format=%aI"
        ).stdout.strip()

        since = since_from_block(rig.consumer_repo)
        result = changes_for(rig, since, rig.consumer_repo)

        assert since == root
        assert result.outcome is ChangesOutcome.LISTED
        assert result.since == parse_since(root)


def test_a_repo_with_no_commits_gives_an_empty_since_that_changes_rejects(
    tmp_path: Path,
) -> None:
    with flow_rig(tmp_path, ConsumedMode.FROM_SOURCE) as rig:
        empty = tmp_path / "empty"
        empty.mkdir()
        git(empty, "init", "-q", "-b", "main")

        since = since_from_block(empty)
        result = changes_for(rig, since, rig.consumer_repo)

        assert since == ""
        assert result.outcome is ChangesOutcome.REJECTED
        assert result.problems[0].code is RejectCode.MALFORMED


def test_the_release_case_versioning_correction_and_withdrawal(
    tmp_path: Path,
) -> None:
    with flow_rig(tmp_path, ConsumedMode.FROM_RELEASE) as rig:
        commit_design(
            rig.consumer_repo, "101-slice.new.md", author="2026-11-02T09:00:00+00:00"
        )
        since = since_from_block(rig.consumer_repo)
        merged = _provider_commit(rig, "interface.txt")
        merge_report = report(rig, _merge_report(merged), at=day(5))
        assert merge_report.outcome is ReportOutcome.RECORDED
        assert _commits(changes_for(rig, since, rig.consumer_repo)) == []

        # The provider tags the reported commit and reports it with the tag name.
        git(rig.provider_repo, "tag", "release-one")
        tagged = git(
            rig.provider_repo, "rev-list", "-n", "1", "release-one"
        ).stdout.strip()
        assert tagged == merged
        versioned = report(
            rig,
            {
                **_merge_report(tagged, "everything in the release"),
                "version": "release-one",
            },
            at=day(6),
        )
        assert versioned.outcome is ReportOutcome.VERSIONED
        (seen,) = changes_for(rig, since, rig.consumer_repo).pairs[0].releases
        assert (seen.version, seen.changed) == (
            "release-one",
            "everything in the release",
        )

        # A correction is seen by a consumer whose since predates it, not after it.
        corrected = report(
            rig,
            {
                "mode": "correct",
                **_merge_report(tagged, "corrected text"),
                "touched": ["fix"],
            },
            at=day(8),
        )
        assert corrected.outcome is ReportOutcome.CORRECTED
        before = changes_for(rig, parse_since(day(7).isoformat()), rig.consumer_repo)
        after = changes_for(rig, parse_since(day(9).isoformat()), rig.consumer_repo)
        assert [r.changed for r in before.pairs[0].releases] == ["corrected text"]
        assert _commits(after) == []

        # A withdrawal removes it from changes.
        withdrawn = report(rig, {"mode": "withdraw", "commit": tagged}, at=day(10))
        assert withdrawn.outcome is ReportOutcome.WITHDRAWN
        assert _commits(changes_for(rig, since, rig.consumer_repo)) == []


def test_two_worktrees_each_see_everything_since_their_own_point(
    tmp_path: Path,
) -> None:
    second = tmp_path / "consumer-second-worktree"
    with flow_rig(
        tmp_path, ConsumedMode.FROM_SOURCE, extra_directories=(second,)
    ) as rig:
        seed = head_of(rig.consumer_repo)
        git(
            rig.consumer_repo,
            "worktree",
            "add",
            "-q",
            "-b",
            "slice-b",
            str(second),
            seed,
        )
        commit_design(
            rig.consumer_repo, "101-slice.a.md", author="2026-11-02T09:00:00+00:00"
        )
        first_report = _provider_commit(rig, "one.txt")
        report(rig, _merge_report(first_report, "first"), at=day(4))
        commit_design(second, "102-slice.b.md", author="2026-11-06T09:00:00+00:00")
        second_report = _provider_commit(rig, "two.txt")
        report(rig, _merge_report(second_report, "second"), at=day(8))

        since_first = since_from_block(rig.consumer_repo)
        since_second = since_from_block(second)

        assert parse_since(since_first) < parse_since(since_second)
        assert _commits(changes_for(rig, since_first, rig.consumer_repo)) == [
            first_report,
            second_report,
        ]
        assert _commits(changes_for(rig, since_second, second)) == [second_report]
        # One project id: the same member answers from either checkout.
        assert (
            changes_for(rig, since_first, second).member
            == changes_for(rig, since_first, rig.consumer_repo).member
        )
