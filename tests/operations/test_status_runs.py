"""Every ``PauseClass`` through ``status``'s run entries, built from ``runs`` documents
(slice 224, 3.6; 261, D11)."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from amoeba.operations.pause_class import PauseClass
from amoeba.operations.runs_document import OpenRun, RunFileFacts
from amoeba.operations.status_models import (
    NextOperation,
    RunEntry,
    RunFileUnreadable,
)
from amoeba.operations.status_placement import PlacedRun
from amoeba.operations.status_runs import LatestRows, RequestStates, classify_runs
from amoeba.store.errors import StoreRowError
from amoeba.store.models import Member, MemberSettings, QuestionKey
from amoeba.store.vocabulary import (
    QuestionState,
    RequestState,
    ResumeOutcome,
    RulesFrom,
)
from amoeba.upstream.squadron.run_list import ListedRun
from operations.runs_doc_support import open_run, project
from operations.status_support import (
    RUN_NOW,
    answer_row,
    in_directory,
    question_row,
    recorded_run,
)

LIMIT = 600.0
MEMBER = Member(
    "demo",
    MemberSettings("member-a", (), (), (), RulesFrom.NAMED),
    RUN_NOW,
    RUN_NOW,
    None,
    "member-a",
    None,
)
PAUSED = "demo-pause-1"
RUNNING = "run-20261111-p6-fe470d63"


@dataclass
class _RunFiles:
    """The run files the gather found: the execution mode of each run that has one."""

    modes: dict[str, str] = field(default_factory=lambda: {})

    def open(self, run: ListedRun) -> OpenRun:
        """``run`` as the document holds it: a paused run with the facts of its run
        file, or with the problem the gather reports when it has none."""
        lookup = project("cf-a") if run.working_directory is not None else None
        if not run.is_paused:
            return open_run(run, lookup)
        mode = self.modes.get(run.run_id)
        if mode is None:
            problem = f"run file runs/{run.run_id}.json does not exist"
            return open_run(run, lookup, run_file_problem=problem)
        facts = RunFileFacts(params={}, execution_mode=mode, working_directory=None)
        return open_run(run, lookup, run_file=facts)


@pytest.fixture
def files() -> _RunFiles:
    return _RunFiles()


def _write_run_file(files: _RunFiles, run_id: str, *, mode: str = "sdk") -> None:
    files.modes[run_id] = mode


def _paused(tmp_path: Path) -> ListedRun:
    return in_directory(recorded_run(PAUSED), tmp_path)


def _key(run: ListedRun) -> QuestionKey:
    assert run.checkpoint is not None
    assert run.checkpoint.paused_at is not None
    return QuestionKey(run.run_id, run.checkpoint.paused_at)


def _entries(
    runs: list[ListedRun], rows: LatestRows, files: _RunFiles
) -> list[RunEntry]:
    placed = tuple(PlacedRun(files.open(run), MEMBER) for run in runs)
    return [item.entry for item in classify_runs(placed, rows, {}, LIMIT, RUN_NOW)]


def _one(run: ListedRun, rows: LatestRows, files: _RunFiles) -> RunEntry:
    (entry,) = _entries([run], rows, files)
    return entry


def test_a_run_that_is_not_paused_has_no_pause(
    tmp_path: Path, files: _RunFiles
) -> None:
    entry = _one(in_directory(recorded_run(RUNNING), tmp_path), {}, files)

    assert entry.pause is None
    assert entry.next is None
    assert entry.status == "running"
    assert entry.checkpoint is None


def test_another_checkpoint_kind_is_other_checkpoint_with_its_kind(
    tmp_path: Path, files: _RunFiles
) -> None:
    run = _paused(tmp_path)
    assert run.checkpoint is not None
    other = replace(
        run, checkpoint=replace(run.checkpoint, kind="interactive_checkpoint")
    )

    entry = _one(other, {}, files)

    assert entry.pause is PauseClass.OTHER_CHECKPOINT
    assert entry.detail == "checkpoint kind interactive_checkpoint"
    assert entry.next is None


def test_an_unknown_kind_is_shown_raw(tmp_path: Path, files: _RunFiles) -> None:
    run = _paused(tmp_path)
    assert run.checkpoint is not None
    odd = replace(run, checkpoint=replace(run.checkpoint, kind="new_kind"))

    assert _one(odd, {}, files).detail == "checkpoint kind new_kind"


def test_an_agent_question_without_text_is_no_question_text(
    tmp_path: Path, files: _RunFiles
) -> None:
    run = _paused(tmp_path)
    assert run.checkpoint is not None
    blank = replace(run, checkpoint=replace(run.checkpoint, question=None))

    entry = _one(blank, {}, files)

    assert entry.pause is PauseClass.NO_QUESTION_TEXT
    assert entry.detail == "the checkpoint has no question text"


def test_a_prompt_only_run_is_prompt_only(tmp_path: Path, files: _RunFiles) -> None:
    _write_run_file(files, PAUSED, mode="prompt-only")

    entry = _one(_paused(tmp_path), {}, files)

    assert entry.pause is PauseClass.PROMPT_ONLY
    assert entry.next is None


def test_an_sdk_run_with_no_row_is_unhandled_and_names_handle_pause(
    tmp_path: Path, files: _RunFiles
) -> None:
    _write_run_file(files, PAUSED)
    run = _paused(tmp_path)

    entry = _one(run, {}, files)

    assert entry.pause is PauseClass.UNHANDLED
    assert entry.next is not None
    assert entry.next.operation is NextOperation.HANDLE_PAUSE
    assert entry.next.run_id == PAUSED
    assert entry.next.paused_at == _key(run).paused_at
    assert entry.next.directory == tmp_path


def test_a_young_claim_is_claim_live_and_has_no_next(
    tmp_path: Path, files: _RunFiles
) -> None:
    run = _paused(tmp_path)
    rows = {
        PAUSED: (question_row(_key(run), QuestionState.CLAIMED, age_seconds=5), None)
    }

    entry = _one(run, rows, files)

    assert entry.pause is PauseClass.CLAIM_LIVE
    assert entry.next is None


def test_a_claim_past_the_limit_is_claim_stale_and_names_handle_pause(
    tmp_path: Path, files: _RunFiles
) -> None:
    run = _paused(tmp_path)
    rows = {
        PAUSED: (
            question_row(_key(run), QuestionState.CLAIMED, age_seconds=LIMIT),
            None,
        )
    }

    entry = _one(run, rows, files)

    assert entry.pause is PauseClass.CLAIM_STALE
    assert entry.next is not None
    assert entry.next.operation is NextOperation.HANDLE_PAUSE


def test_a_waiting_question_is_waiting_on_the_pm_with_no_next_here(
    tmp_path: Path, files: _RunFiles
) -> None:
    run = _paused(tmp_path)
    rows = {PAUSED: (question_row(_key(run), QuestionState.WAITING_ON_PM), None)}

    entry = _one(run, rows, files)

    assert entry.pause is PauseClass.WAITING_ON_PM
    assert entry.next is None


@pytest.mark.parametrize(
    ("outcome", "detail", "shown"),
    [
        (None, None, "not attempted"),
        (ResumeOutcome.REFUSED, "run is busy", "refused: run is busy"),
    ],
)
def test_an_answer_not_handed_over_is_answered_unresumed_and_names_handle_pause(
    tmp_path: Path,
    files: _RunFiles,
    outcome: ResumeOutcome | None,
    detail: str | None,
    shown: str,
) -> None:
    run = _paused(tmp_path)
    key = _key(run)
    rows = {
        PAUSED: (
            question_row(key, QuestionState.ANSWERED),
            answer_row(key, outcome, detail=detail),
        )
    }

    entry = _one(run, rows, files)

    assert entry.pause is PauseClass.ANSWERED_UNRESUMED
    assert entry.detail == shown
    assert entry.next is not None
    assert entry.next.operation is NextOperation.HANDLE_PAUSE


@pytest.mark.parametrize(
    "outcome", [ResumeOutcome.RESUMED, ResumeOutcome.NOT_DELIVERED]
)
def test_a_handed_over_answer_is_settled_with_its_outcome(
    tmp_path: Path, files: _RunFiles, outcome: ResumeOutcome
) -> None:
    run = _paused(tmp_path)
    key = _key(run)
    rows = {
        PAUSED: (question_row(key, QuestionState.ANSWERED), answer_row(key, outcome))
    }

    entry = _one(run, rows, files)

    assert entry.pause is PauseClass.SETTLED
    assert entry.detail == outcome.value
    assert entry.next is None


def test_a_row_of_an_earlier_pause_does_not_hide_a_missed_hook_at_this_one(
    tmp_path: Path, files: _RunFiles
) -> None:
    _write_run_file(files, PAUSED)
    run = _paused(tmp_path)
    earlier = QuestionKey(PAUSED, "2026-11-09T08:00:00+00:00")
    rows = {
        PAUSED: (
            question_row(earlier, QuestionState.ANSWERED),
            answer_row(earlier, ResumeOutcome.RESUMED),
        )
    }

    assert _one(run, rows, files).pause is PauseClass.UNHANDLED


def test_an_unreadable_run_file_is_that_runs_entry_and_the_rest_are_shown(
    tmp_path: Path, files: _RunFiles
) -> None:
    broken = _paused(tmp_path)  # no run file written for it
    fine = in_directory(recorded_run(RUNNING), tmp_path)

    entries = _entries([broken, fine], {}, files)

    assert entries[0].pause is RunFileUnreadable.RUN_FILE_UNREADABLE
    assert entries[0].detail is not None
    assert "does not exist" in entries[0].detail
    assert entries[0].next is None
    assert entries[1].run_id == RUNNING


def test_the_run_file_is_not_read_for_a_run_that_has_a_row(
    tmp_path: Path, files: _RunFiles
) -> None:
    run = _paused(tmp_path)  # no run file: reading it would be unreadable
    rows = {PAUSED: (question_row(_key(run), QuestionState.WAITING_ON_PM), None)}

    assert _one(run, rows, files).pause is PauseClass.WAITING_ON_PM


HELD_REQUEST = "request-held"
START_ATTEMPT = RUN_NOW - timedelta(minutes=3)


def _held_entry(
    tmp_path: Path,
    files: _RunFiles,
    requests: RequestStates,
    *,
    attempted: datetime | None = None,
) -> RunEntry:
    """The entry of a run held on ``HELD_REQUEST`` (slice 242, D9)."""
    run = _paused(tmp_path)
    row = replace(
        question_row(_key(run), QuestionState.WAITING_ON_REQUEST),
        request_id=HELD_REQUEST,
        start_attempted_at=attempted,
    )
    placed = (PlacedRun(files.open(run), MEMBER),)
    (item,) = classify_runs(placed, {PAUSED: (row, None)}, requests, LIMIT, RUN_NOW)
    return item.entry


def test_a_held_run_shows_its_request_and_the_requests_state_with_no_next(
    tmp_path: Path, files: _RunFiles
) -> None:
    entry = _held_entry(tmp_path, files, {HELD_REQUEST: RequestState.ACCEPTED})

    assert entry.pause is PauseClass.WAITING_ON_REQUEST
    assert entry.detail == f"waiting on request {HELD_REQUEST} (accepted)"
    assert entry.next is None


def test_a_held_run_shows_when_handle_pause_was_last_started(
    tmp_path: Path, files: _RunFiles
) -> None:
    entry = _held_entry(
        tmp_path,
        files,
        {HELD_REQUEST: RequestState.DONE},
        attempted=START_ATTEMPT,
    )

    assert entry.detail == (
        f"waiting on request {HELD_REQUEST} (done); handle_pause last started "
        f"{START_ATTEMPT.isoformat()}"
    )
    assert entry.next is None


def test_a_held_run_whose_request_is_gone_shows_gone(
    tmp_path: Path, files: _RunFiles
) -> None:
    entry = _held_entry(tmp_path, files, {HELD_REQUEST: None})

    assert entry.detail == f"waiting on request {HELD_REQUEST} (gone)"


def test_a_held_run_whose_request_state_was_not_read_is_a_store_row_error(
    tmp_path: Path, files: _RunFiles
) -> None:
    with pytest.raises(StoreRowError, match=HELD_REQUEST):
        _held_entry(tmp_path, files, {})
