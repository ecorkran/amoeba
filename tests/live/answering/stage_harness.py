"""The real ``handle_pause`` over the real ``sq`` and real models (slice 223, task 9.3).

Restored from the slice 144 stage harness and rewritten: the production code is the
``amoeba handle_pause`` command, run as a subprocess in a throwaway member whose
checkout is the frozen sources fixture (rules and plan for slice 132), registered with
its own Context Forge data directory and ``AMOEBA_HOME``. Each case makes one real
pause whose question the pipeline's model is told to reply with, calls
``handle_pause``, and reads the record. Nothing retries and a wrong result fails the
test.
"""

from __future__ import annotations

import json
import shutil
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from answering.sources_repo import build_sources_repo
from git_repo import git
from live_settings import LiveSettings

from amoeba.answering.values import DeclineReason
from amoeba.store.answers import add_pm_answer
from amoeba.store.models import QuestionKey
from amoeba.store.question_json import parse_passages
from amoeba.store.questions import NewQuestion, insert_question
from amoeba.store.store import Store
from amoeba.upstream.squadron.launch import mint_run_id
from amoeba.upstream.squadron.run_outcome import RunOutcome, RunOutcomeDocument
from live.pause.harness import (
    PauseWorld,
    build_world,
    question_pipeline,
    result_of,
    run_amoeba,
    start_pause,
    store_rows,
)

#: The slice the fixture's rules and plan are about, and its label (what
#: ``handle_pause`` records).
SLICE_INDEX = "132"
SLICE_LABEL = "132 Pipeline Supervisor"
#: A slice the plan does not hold; PM answers recorded on it are "another slice".
OTHER_SLICE_LABEL = "200 Web Console"
PASSAGES_MAX_CHARS = 1_000_000


@dataclass(frozen=True)
class Settled:
    """What ``handle_pause`` did with a real pause, and what it recorded."""

    result: dict[str, object]
    state: str
    waiting_reason: str | None
    waiting_detail: str | None
    answer: str | None
    cited: tuple[str, ...]
    verdict: str | None
    #: The passage ids that came from a PM answer, by the question key they came from.
    pm_passages: dict[str, str]


@dataclass(frozen=True)
class LivePause:
    """A throwaway member holding a real, un-handled pause on a given question."""

    world: PauseWorld
    run_id: str
    member_id: str

    def seed_pm_answer(
        self, slice_label: str, question: str, answer: str, when: datetime
    ) -> QuestionKey:
        """A question the PM answered, as precedent for the pause under test."""
        key = QuestionKey(
            f"seeded-{abs(hash((question, slice_label)))}", when.isoformat()
        )
        seeded = NewQuestion(
            key=key,
            member_id=self.member_id,
            question=question,
            checkout=str(self.world.repo),
            slice_label=slice_label,
            source_commit=None,
            passages=None,
            answering_run_id=None,
            waiting_reason=DeclineReason.NO_ANSWER_ON_FILE,
            waiting_detail=None,
        )
        with Store.open(self.world.store) as store, store.write() as transaction:
            insert_question(transaction, seeded, now=when)
            add_pm_answer(transaction, key, answer, now=when)
        return key

    def settle(self) -> Settled:
        """Call ``handle_pause`` on the pause and read what it recorded."""
        completed = run_amoeba(self.world, "handle_pause", self.run_id)
        assert completed.returncode == 0, completed.stderr
        result = result_of(completed)
        (row,) = store_rows(
            self.world,
            "SELECT state, waiting_reason, waiting_detail, evidence, passages "
            f"FROM questions WHERE run_id = '{self.run_id}'",
        )
        state, reason, detail, evidence, passages = row
        answers = store_rows(
            self.world,
            "SELECT answer, cited FROM answers "
            f"WHERE run_id = '{self.run_id}' AND answered_by = 'answerer'",
        )
        verdict = None if evidence is None else json.loads(str(evidence))["verdict"]
        refs = () if passages is None else parse_passages(passages)
        return Settled(
            result=result,
            state=str(state),
            waiting_reason=None if reason is None else str(reason),
            waiting_detail=None if detail is None else str(detail),
            answer=str(answers[0][0]) if answers else None,
            cited=tuple(json.loads(str(answers[0][1]))) if answers else (),
            verdict=None if verdict is None else str(verdict),
            pm_passages={
                ref.question_id: ref.id for ref in refs if ref.question_id is not None
            },
        )


def build_live_pause(
    tmp_path: Path, amoeba_home: Path, live: LiveSettings, question: str
) -> LivePause:
    """The fixture member, registered, with its run paused on ``question``."""
    repo = _fixture_member(tmp_path)
    world = build_world(
        tmp_path,
        amoeba_home,
        live,
        repo=repo,
        passages_max_chars=PASSAGES_MAX_CHARS,
    )
    pipeline = question_pipeline(tmp_path, "pause", question, sliced=True)
    run_id = mint_run_id(datetime.now(UTC))
    started = start_pause(
        world, run_id, opt_out=True, pipeline=pipeline, slice_index=SLICE_INDEX
    )
    assert isinstance(started.poll, RunOutcomeDocument), started.sq_output
    assert started.poll.outcome is RunOutcome.PAUSED, started.sq_output
    (member,) = store_rows(world, "SELECT project_id FROM members")
    return LivePause(world, run_id, str(member[0]))


def _fixture_member(parent: Path) -> Path:
    """A git repository holding the frozen sources fixture, committed on ``main``."""
    template = Path(tempfile.mkdtemp(prefix="amoeba-live-sources-"))
    try:
        built = build_sources_repo(template / "repo").path
        repo = parent / "member"
        shutil.copytree(built, repo)
    finally:
        shutil.rmtree(template, ignore_errors=True)
    git(repo, "status", "--short")
    return repo
