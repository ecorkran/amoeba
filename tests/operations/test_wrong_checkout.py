"""``handle_pause`` called outside the run's recorded directory (slice 228, D10)."""

from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path

from store.question_support import NOW, claimed_question, waiting_question

from amoeba.operations.handle_pause import handle_pause
from amoeba.operations.pause_models import (
    HandlePauseOutcome,
    HandlePauseResult,
    SkipReason,
)
from amoeba.store.answers import add_pm_answer, answers_of
from amoeba.store.questions import get_question, insert_question
from amoeba.store.vocabulary import QuestionState
from operations.handle_rig import KEY, PROJECT_ID, RUN, World, world
from operations.pause_support import START


def _record_started_in(w: World, directory: Path) -> None:
    path = w.runs_dir / f"{RUN}.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    document["working_directory"] = str(directory)
    path.write_text(json.dumps(document), encoding="utf-8")


def _handle_from(w: World, directory: Path) -> HandlePauseResult:
    return handle_pause(w.store, w.config, RUN, directory=directory, deps=w.deps)


def _second_checkout(tmp_path: Path) -> Path:
    second = tmp_path / "second-worktree"
    second.mkdir()
    return second


def test_a_call_from_a_second_directory_skips_naming_both_and_writes_no_row(
    tmp_path: Path,
) -> None:
    with world(tmp_path) as w:
        _record_started_in(w, w.directory)
        second = _second_checkout(tmp_path)

        result = _handle_from(w, second)

        assert result.outcome is HandlePauseOutcome.SKIPPED
        assert result.skip_reason is SkipReason.WRONG_CHECKOUT
        assert result.detail == (
            f"called from {second}; the run was started in {w.directory}"
        )
        with w.store.read() as transaction:
            assert get_question(transaction, KEY) is None
        assert w.spawned.argvs == []


def test_a_dead_claim_is_not_resumed_from_a_second_directory(tmp_path: Path) -> None:
    with world(tmp_path) as w:
        _record_started_in(w, w.directory)
        with w.store.write() as transaction:
            insert_question(
                transaction,
                claimed_question(KEY, member_id=PROJECT_ID),
                now=START - timedelta(days=1),
            )

        result = _handle_from(w, _second_checkout(tmp_path))

        assert result.skip_reason is SkipReason.WRONG_CHECKOUT
        assert w.spawned.argvs == []
        with w.store.read() as transaction:
            row = get_question(transaction, KEY)
        assert row is not None
        assert row.state is QuestionState.CLAIMED


def test_an_unresumed_answer_is_not_resumed_from_a_second_directory(
    tmp_path: Path,
) -> None:
    with world(tmp_path) as w:
        _record_started_in(w, w.directory)
        with w.store.write() as transaction:
            insert_question(
                transaction, waiting_question(KEY, member_id=PROJECT_ID), now=NOW
            )
            add_pm_answer(transaction, KEY, "an answer", now=NOW, via=None)

        result = _handle_from(w, _second_checkout(tmp_path))

        assert result.skip_reason is SkipReason.WRONG_CHECKOUT
        assert w.spawned.resumes == []
        with w.store.read() as transaction:
            (answer,) = answers_of(transaction, KEY)
        assert answer.resume_outcome is None


def test_from_the_recorded_directory_it_behaves_as_before(tmp_path: Path) -> None:
    with world(tmp_path) as w:
        _record_started_in(w, w.directory)

        result = w.handle()

        assert result.outcome is HandlePauseOutcome.RESUMED


def test_a_run_file_without_the_directory_behaves_as_before(tmp_path: Path) -> None:
    with world(tmp_path) as w:
        path = w.runs_dir / f"{RUN}.json"
        document = json.loads(path.read_text(encoding="utf-8"))
        del document["working_directory"]  # a run from before sq 0.24.24
        path.write_text(json.dumps(document), encoding="utf-8")

        result = _handle_from(w, _second_checkout(tmp_path))

        assert result.skip_reason is not SkipReason.WRONG_CHECKOUT


def test_a_recorded_directory_that_no_longer_exists_says_so(tmp_path: Path) -> None:
    with world(tmp_path) as w:
        gone = tmp_path / "removed-worktree"
        _record_started_in(w, gone)

        result = w.handle()

        assert result.skip_reason is SkipReason.WRONG_CHECKOUT
        assert result.detail is not None
        assert str(gone) in result.detail
        assert "no longer exists" in result.detail
        assert "sq run --resume" in result.detail


def test_a_symlinked_path_to_the_same_directory_passes(tmp_path: Path) -> None:
    with world(tmp_path) as w:
        link = tmp_path / "link-to-checkout"
        link.symlink_to(w.directory, target_is_directory=True)
        _record_started_in(w, link)

        result = w.handle()

        assert result.outcome is HandlePauseOutcome.RESUMED


def test_a_subdirectory_of_the_runs_checkout_passes(tmp_path: Path) -> None:
    with world(tmp_path) as w:
        subdirectory = w.directory / "src"
        subdirectory.mkdir()
        _record_started_in(w, subdirectory)

        result = w.handle()

        assert result.outcome is HandlePauseOutcome.RESUMED


def test_a_linked_worktree_nested_inside_the_checkout_is_another_checkout(
    tmp_path: Path,
) -> None:
    with world(tmp_path) as w:
        nested = w.directory / "worktrees" / "second"
        nested.mkdir(parents=True)
        (nested / ".git").write_text("gitdir: elsewhere\n", encoding="utf-8")
        _record_started_in(w, nested)

        result = w.handle()

        assert result.skip_reason is SkipReason.WRONG_CHECKOUT
