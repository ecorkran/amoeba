"""``prune`` (slice 228, D9): settled and orphaned scratch and logs, by age."""

from __future__ import annotations

import os
from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from store.question_support import (
    NOW,
    claimed_question,
    seed_members,
    waiting_question,
)

from amoeba.answering.values import DeclineReason
from amoeba.config.home import StateLayout
from amoeba.operations.decisions import DecisionsOutcome, decisions
from amoeba.operations.dismiss import dismiss
from amoeba.operations.prune import prune
from amoeba.operations.prune_models import PruneReport
from amoeba.store.answers import add_pm_answer, answers_of, record_resume
from amoeba.store.models import QuestionKey
from amoeba.store.questions import insert_question, settle_waiting
from amoeba.store.store import Store
from amoeba.store.vocabulary import ResumeOutcome
from operations.pause_support import build_deps

CLOCK = datetime(2026, 11, 12, 12, 0, tzinfo=UTC)
AFTER_DAYS = 30
OLD = 40
YOUNG = 5
SETTLED_KEY = QuestionKey("run-settled", "2026-10-01T10:00:00+00:00")
OPEN_KEY = QuestionKey("run-open", "2026-10-01T11:00:00+00:00")
SETTLED_ANSWERING = "answering-settled"
OPEN_ANSWERING = "answering-open"
ORPHAN_ANSWERING = "answering-orphan"
YOUNG_ANSWERING = "answering-young-settled"


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    with Store.open(tmp_path / "amoeba.sqlite3") as opened:
        seed_members(opened)
        yield opened


@pytest.fixture
def layout(tmp_path: Path) -> StateLayout:
    state = tmp_path / "state"
    return StateLayout(
        state_home=state,
        store_path=state / "amoeba.sqlite3",
        answering_dir=state / "answering",
        logs_dir=state / "logs",
        calls_log_dir=state / "logs" / "calls",
        legacy_home=None,
    )


def _age(path: Path, days: float) -> None:
    stamp = (CLOCK - timedelta(days=days)).timestamp()
    os.utime(path, (stamp, stamp))


def _file(path: Path, days: float) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("x", encoding="utf-8")
    _age(path, days)
    return path


def _scratch(layout: StateLayout, name: str, days: float) -> Path:
    directory = layout.answering_dir / name
    _file(directory / "input.json", days)
    _age(directory, days)
    return directory


def _answering_log(layout: StateLayout, name: str, days: float) -> list[Path]:
    base = layout.logs_dir / "answering"
    return [
        _file(base / f"{name}{suffix}", days)
        for suffix in (".stdout.log", ".stderr.log")
    ]


def _resume_log(layout: StateLayout, run_id: str, days: float) -> Path:
    return _file(layout.logs_dir / "resume" / run_id / "1-20261001.stdout.log", days)


def _open_question(store: Store, key: QuestionKey, answering_run_id: str) -> None:
    with store.write() as transaction:
        insert_question(
            transaction,
            claimed_question(key, answering_run_id=answering_run_id),
            now=NOW,
        )


def _settle(store: Store, key: QuestionKey) -> None:
    result = dismiss(
        store, {"run_id": key.run_id, "reason": "done with it"}, clock=lambda: NOW
    )
    assert result.outcome.value == "dismissed"


def _prune(store: Store, layout: StateLayout) -> PruneReport:
    return prune(store, layout, CLOCK, AFTER_DAYS)


def test_settled_and_orphan_scratch_with_their_logs_are_pruned(
    store: Store, layout: StateLayout
) -> None:
    _open_question(store, SETTLED_KEY, SETTLED_ANSWERING)
    _settle(store, SETTLED_KEY)
    settled = _scratch(layout, SETTLED_ANSWERING, OLD)
    orphan = _scratch(layout, ORPHAN_ANSWERING, OLD)
    logs = _answering_log(layout, SETTLED_ANSWERING, OLD) + _answering_log(
        layout, ORPHAN_ANSWERING, OLD
    )

    report = _prune(store, layout)

    assert not settled.exists()
    assert not orphan.exists()
    assert not any(log.exists() for log in logs)
    assert report.problems == ()
    assert report.removed == 6


def test_an_open_questions_scratch_and_logs_are_kept_at_any_age(
    store: Store, layout: StateLayout
) -> None:
    _open_question(store, OPEN_KEY, OPEN_ANSWERING)
    scratch = _scratch(layout, OPEN_ANSWERING, OLD * 10)
    logs = _answering_log(layout, OPEN_ANSWERING, OLD * 10)
    resume = _resume_log(layout, OPEN_KEY.run_id, OLD * 10)

    _prune(store, layout)

    assert scratch.exists()
    assert all(log.exists() for log in logs)
    assert resume.exists()


def test_a_waiting_questions_evidence_is_kept_and_an_unresumed_answers_too(
    store: Store, layout: StateLayout
) -> None:
    _open_question(store, OPEN_KEY, OPEN_ANSWERING)
    with store.write() as transaction:
        settle_waiting(
            transaction,
            OPEN_KEY,
            OPEN_ANSWERING,
            reason=DeclineReason.CHECK_SAID_NO,
            detail="no",
            evidence=None,
            now=NOW,
        )
        add_pm_answer(transaction, OPEN_KEY, "an answer", now=NOW, via=None)
    scratch = _scratch(layout, OPEN_ANSWERING, OLD)

    _prune(store, layout)

    assert scratch.exists()


def test_young_entries_are_kept_even_when_settled_or_orphaned(
    store: Store, layout: StateLayout
) -> None:
    _open_question(store, SETTLED_KEY, YOUNG_ANSWERING)
    _settle(store, SETTLED_KEY)
    settled = _scratch(layout, YOUNG_ANSWERING, YOUNG)
    orphan = _scratch(layout, ORPHAN_ANSWERING, YOUNG)
    log = _answering_log(layout, ORPHAN_ANSWERING, YOUNG)[0]
    resume = _resume_log(layout, SETTLED_KEY.run_id, YOUNG)

    report = _prune(store, layout)

    assert all(path.exists() for path in (settled, orphan, log, resume))
    assert report.removed == 0


def test_a_settled_runs_resume_logs_go_and_so_does_the_emptied_directory(
    store: Store, layout: StateLayout
) -> None:
    _open_question(store, SETTLED_KEY, SETTLED_ANSWERING)
    _settle(store, SETTLED_KEY)
    old = _resume_log(layout, SETTLED_KEY.run_id, OLD)
    young = _resume_log(layout, "run-other", YOUNG)
    directory = old.parent

    _prune(store, layout)

    assert not old.exists()
    assert not directory.exists()
    assert young.exists()
    assert (layout.logs_dir / "resume").is_dir()


@pytest.mark.skipif(os.geteuid() == 0, reason="root removes anything")
def test_an_unremovable_entry_is_named_and_the_rest_still_prune(
    store: Store, layout: StateLayout
) -> None:
    stuck = _scratch(layout, "answering-stuck", OLD)
    fine = _answering_log(layout, ORPHAN_ANSWERING, OLD)[0]
    layout.answering_dir.chmod(0o555)  # entries cannot be removed from it
    try:
        report = _prune(store, layout)
    finally:
        layout.answering_dir.chmod(0o755)

    assert stuck.exists()
    assert not fine.exists()
    (problem,) = report.problems
    assert str(stuck) in problem


def test_a_pruned_resume_log_stays_named_in_the_answer_and_decisions_still_lists(
    store: Store, layout: StateLayout, tmp_path: Path
) -> None:
    with store.write() as transaction:
        insert_question(transaction, waiting_question(SETTLED_KEY), now=NOW)
        seq = add_pm_answer(transaction, SETTLED_KEY, "an answer", now=NOW, via=None)
    log = _resume_log(layout, SETTLED_KEY.run_id, OLD)
    with store.write() as transaction:
        record_resume(
            transaction,
            seq,
            ResumeOutcome.RESUMED,
            detail=None,
            log=str(log),
            at=NOW,
        )

    _prune(store, layout)

    assert not log.exists()
    with store.read() as transaction:
        (answer,) = answers_of(transaction, SETTLED_KEY)
    assert answer.resume_log == str(log)
    rig = build_deps(tmp_path, polls={}, spawns=[])
    deps = replace(rig.deps, project_names=lambda: {"member-a": "a", "member-b": "b"})
    result = decisions(store, {}, deps=deps)
    assert result.outcome is DecisionsOutcome.LISTED
    assert [record.seq for record in result.records] == [seq]


def test_calls_log_days_go_by_their_date_not_their_mtime(
    store: Store, layout: StateLayout
) -> None:
    calls = layout.calls_log_dir
    old_day = _file(calls / "2026-09-01.jsonl", YOUNG)  # old date, fresh mtime
    cutoff_day = (CLOCK - timedelta(days=AFTER_DAYS)).strftime("%Y-%m-%d")
    on_cutoff = _file(calls / f"{cutoff_day}.jsonl", OLD * 5)  # on the cutoff day
    today = _file(calls / "2026-11-12.jsonl", OLD * 5)  # new date, ancient mtime

    _prune(store, layout)

    assert not old_day.exists()
    assert on_cutoff.exists()
    assert today.exists()


def test_a_calls_directory_file_that_is_not_a_day_file_goes_by_mtime(
    store: Store, layout: StateLayout
) -> None:
    stray_old = _file(layout.calls_log_dir / "notes.txt", OLD)
    stray_young = _file(layout.calls_log_dir / "scratch.txt", YOUNG)

    _prune(store, layout)

    assert not stray_old.exists()
    assert stray_young.exists()


def test_other_log_files_and_their_emptied_directory_are_pruned_when_old(
    store: Store, layout: StateLayout
) -> None:
    old = _file(layout.logs_dir / "mcp" / "20261001.log", OLD)
    young_dir_file = _file(layout.logs_dir / "mcp-young" / "20261110.log", YOUNG)
    top_level_old = _file(layout.logs_dir / "stray.log", OLD)

    _prune(store, layout)

    assert not old.exists()
    assert not old.parent.exists()
    assert young_dir_file.exists()
    assert not top_level_old.exists()
    assert layout.logs_dir.is_dir()


def test_the_named_log_directories_stay_when_emptied(
    store: Store, layout: StateLayout
) -> None:
    _file(layout.calls_log_dir / "2026-01-01.jsonl", OLD)
    _answering_log(layout, ORPHAN_ANSWERING, OLD)

    _prune(store, layout)

    assert layout.calls_log_dir.is_dir()
    assert (layout.logs_dir / "answering").is_dir()


def test_a_set_aside_legacy_store_is_never_pruned(
    store: Store, layout: StateLayout
) -> None:
    aside = _file(layout.state_home / "amoeba.sqlite3.legacy-20261001T000000Z", OLD * 5)

    _prune(store, layout)

    assert aside.exists()


def test_a_missing_state_directory_is_nothing_to_prune(
    store: Store, layout: StateLayout
) -> None:
    report = _prune(store, layout)

    assert report == PruneReport(removed=0, problems=())


def test_a_second_call_within_the_interval_does_not_walk_again(
    store: Store, layout: StateLayout
) -> None:
    layout.state_home.mkdir(parents=True)
    _prune(store, layout)
    orphan = _scratch(layout, ORPHAN_ANSWERING, OLD)

    soon = prune(store, layout, CLOCK + timedelta(minutes=30), AFTER_DAYS)

    assert soon == PruneReport(removed=0, problems=())
    assert orphan.exists()


def test_a_call_after_the_interval_walks_again(
    store: Store, layout: StateLayout
) -> None:
    layout.state_home.mkdir(parents=True)
    _prune(store, layout)
    orphan = _scratch(layout, ORPHAN_ANSWERING, OLD)

    later = prune(store, layout, CLOCK + timedelta(hours=2), AFTER_DAYS)

    assert later.removed > 0
    assert not orphan.exists()
