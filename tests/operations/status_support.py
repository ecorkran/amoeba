"""Fakes and builders for the ``status`` tests (slice 224).

``FakeCf`` answers ``cf get --json`` per working directory from the real recordings
(the project id is the one substitution), counting the calls per directory.
``status_deps`` builds ``Deps`` with a scripted ``list_runs`` and ``project_names``.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from enum import Enum, auto
from pathlib import Path

from cf_fixtures import (
    DEFAULT_WORKTREE,
    OUTSIDE_ANY_PROJECT,
    failure,
    fixture_document,
    replay,
)
from fake_sq import LIST_MIXED, RUNS_LIST_FIXTURES

from amoeba.answering.values import AnsweredBy
from amoeba.operations.deps import Deps
from amoeba.store.models import AnswerRecord, QuestionKey, QuestionRecord
from amoeba.store.vocabulary import QuestionState, ResumeOutcome
from amoeba.upstream.context_forge.cli_call import CfCallFailed
from amoeba.upstream.context_forge.projects import ProjectNames
from amoeba.upstream.squadron.run_list import ListedRun, RunListProblem, parse_listing
from operations.pause_support import build_deps


def recorded_runs() -> list[ListedRun]:
    """The real ``sq runs list --json`` selection, parsed by the production reader."""
    text = (RUNS_LIST_FIXTURES / LIST_MIXED).read_text(encoding="utf-8")
    runs = parse_listing(text)
    assert isinstance(runs, list), runs
    return runs


def recorded_run(run_id: str) -> ListedRun:
    """One recorded run by id."""
    (found,) = [run for run in recorded_runs() if run.run_id == run_id]
    return found


def in_directory(run: ListedRun, directory: Path | None) -> ListedRun:
    """``run`` as if it had been started in ``directory``."""
    return replace(run, working_directory=directory)


RUN_NOW = datetime(2026, 11, 11, 12, 0, tzinfo=UTC)


def question_row(
    key: QuestionKey,
    state: QuestionState,
    *,
    member_id: str = "member-a",
    age_seconds: float = 0.0,
) -> QuestionRecord:
    """A question row ``age_seconds`` old at ``RUN_NOW`` (``claimed_at`` and
    ``updated_at`` both)."""
    moment = RUN_NOW - timedelta(seconds=age_seconds)
    return QuestionRecord(
        key=key,
        member_id=member_id,
        question="Which?",
        checkout="/work",
        state=state,
        answering_run_id="answering-1",
        waiting_reason=None,
        waiting_detail=None,
        slice_label=None,
        source_commit=None,
        passages=(),
        evidence=None,
        claimed_at=moment,
        updated_at=moment,
    )


def answer_row(
    key: QuestionKey,
    outcome: ResumeOutcome | None,
    *,
    detail: str | None = None,
    seq: int = 1,
) -> AnswerRecord:
    """An answer row with the given resume outcome."""
    return AnswerRecord(
        seq=seq,
        key=key,
        answered_by=AnsweredBy.ANSWERER,
        answer="Yes.",
        cited=None,
        recorded_at=RUN_NOW,
        resume_outcome=outcome,
        resume_detail=detail,
        resume_log=None,
        resume_at=None,
    )


class CfAnswer(Enum):
    """What ``FakeCf`` does for a directory that is not given a project id."""

    NOT_A_PROJECT = auto()
    FAILS = auto()
    TIMES_OUT = auto()


@dataclass
class FakeCf:
    """A ``CfRun``: ``cf get --json`` in a directory gives that directory's answer."""

    by_directory: Mapping[Path, str | CfAnswer]
    calls: list[Path] = field(default_factory=lambda: [])

    def __call__(
        self, argv: Sequence[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        directory = kwargs["cwd"]
        assert isinstance(directory, Path), "status asks cf from a run's directory"
        self.calls.append(directory)
        answer = self.by_directory[directory]
        if answer is CfAnswer.NOT_A_PROJECT:
            return replay(argv, OUTSIDE_ANY_PROJECT)
        if answer is CfAnswer.FAILS:
            return failure(argv)
        if answer is CfAnswer.TIMES_OUT:
            raise subprocess.TimeoutExpired(list(argv), 1.0)
        assert isinstance(answer, str)
        document = {**fixture_document(DEFAULT_WORKTREE), "id": answer}
        return subprocess.CompletedProcess(list(argv), 0, json.dumps(document), "")


def status_deps(
    tmp_path: Path,
    *,
    cf: Callable[..., subprocess.CompletedProcess[str]],
    runs: list[ListedRun] | RunListProblem,
    names: ProjectNames | CfCallFailed,
    answering_dir: Path | None = None,
) -> Deps:
    """``Deps`` for ``status``: the given ``cf``, listing and names, and fakes else."""
    base = build_deps(tmp_path, polls={}, spawns=[]).deps
    return replace(
        base,
        cf_run=cf,
        list_runs=lambda: runs,
        project_names=lambda: names,
        answering_dir=answering_dir or base.answering_dir,
    )
