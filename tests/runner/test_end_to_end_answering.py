"""The answerer end to end on the stub tier: a question paused slice, answered (144).

The tenant, the stage, the store and the gate are production code; ``sq`` and ``cf``
are the stubs on ``PATH``. The slice's own run pauses on a question
(``RUN_SCRIPT_ENV``); the answering run is scripted apart (``ANSWER_SCRIPT_ENV``).
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any

import pytest
from cli_harness import run_cli
from sq_stub import (
    ANSWER_OUTCOME_ENV,
    ANSWER_SCRIPT_ENV,
    RUN_SECONDS_ENV,
    STUB_STATE_RELATIVE,
    write_run_script,
)
from sq_stub_resume import RESUME_ARGV_LOG_ENV
from sq_stub_scripts import (
    agent_question_run,
    answering_run,
    check_reply,
    declining_answer_reply,
    empty_reviews,
    proposed_answer_reply,
)

from amoeba.inspection.core import blocked_rows
from amoeba.inspection.listing import ListingRequest, Row
from amoeba.process.recovery import reconcile
from amoeba.process.supervisor import build_observer_registry
from amoeba.runner.answering import stage as stage_module
from amoeba.runner.answering.finish import QuestionOutcome
from amoeba.runner.answering.gate import compose_instructions
from amoeba.runner.answering.launch import LaunchContext, LaunchStatus
from amoeba.runner.answering.stage import AnsweringStage, StageResult
from amoeba.runner.budget import TickBudget
from amoeba.runner.faults import TickFaults
from amoeba.store import (
    AnsweredBy,
    AnsweringLaunch,
    CommandKind,
    DeclineReason,
    JournalEntry,
    JournalOutcome,
    NodeStatus,
    QuestionRecord,
    QuestionState,
    Store,
)
from amoeba.store.paths import project_store_path
from runner.git_repo import commit_file
from runner.resolutions.resolution_support import resolve_block
from runner.test_end_to_end import GRACE_SECONDS, PROJECT, Scenario

QUESTION = "Which branch should I merge into?"
ANSWER = "Use main."
RULES_TEXT = "# Rules\nMerge into main.\n"
PLAN_FILE = "project-documents/user/architecture/120-slices.demo.md"

ANSWERER_CONFIG = f"""\
projects:
  {PROJECT}:
    pipeline: p456
    answerer:
      answer_limit: 3
      reserved_terms: []
      rules_paths: [CLAUDE.md]
      passages_max_chars: 100000
      answer_model: answer-alias
      check_model: check-alias
      max_concurrent_runs: 2
      max_cost_usd: 0.5
"""


@pytest.fixture
def scenario(tmp_path: Path, store: Store, monkeypatch: pytest.MonkeyPatch) -> Scenario:
    built = Scenario(tmp_path, store, monkeypatch)
    commit_file(built.world.root, "CLAUDE.md", RULES_TEXT, "add the rules")
    # The plan directory the sources reader lists must exist at the target commit.
    commit_file(built.world.root, PLAN_FILE, "# Plan\nNothing yet.\n", "add a plan")
    assert built.settings.project_config_path is not None
    built.settings.project_config_path.write_text(ANSWERER_CONFIG)
    built.script(agent_question_run(QUESTION), outcome="paused")
    return built


def _script_answering(
    scenario: Scenario,
    answer: dict[str, object] | None,
    check: dict[str, object] | None,
    outcome: str = "completed",
) -> None:
    script = answering_run(answer, check)
    path = write_run_script(
        scenario.tmp_path / "answer-script.json",
        files=script.files,
        document=script.document,
    )
    scenario.monkeypatch.setenv(ANSWER_SCRIPT_ENV, str(path))
    scenario.monkeypatch.setenv(ANSWER_OUTCOME_ENV, outcome)


def _answer_entries(scenario: Scenario) -> list[JournalEntry]:
    found = scenario.store.journal_entries(PROJECT, node_id=scenario.node.id)
    return [e for e in found if e.kind is CommandKind.SQ_ANSWER]


def _question(scenario: Scenario) -> QuestionRecord | None:
    found = scenario.store.questions(PROJECT, node_id=scenario.node.id)
    return found[0] if found else None


def _settled(scenario: Scenario) -> bool:
    record = _question(scenario)
    return record is not None and record.state in (
        QuestionState.ANSWERED,
        QuestionState.DECLINED,
    )


def test_a_question_is_answered_by_the_answerer_and_the_slice_resumes_answering(
    scenario: Scenario, tmp_path: Path
) -> None:
    argv_log = tmp_path / "resume-argv.jsonl"
    scenario.monkeypatch.setenv(RESUME_ARGV_LOG_ENV, str(argv_log))
    _script_answering(
        scenario,
        proposed_answer_reply(ANSWER, ["P1"]),
        check_reply("yes", "the rules say so"),
    )

    scenario.tick_until("the question to be answered", lambda: _settled(scenario))
    scenario.script(empty_reviews())
    scenario.tick_until("the slice to finish", lambda: scenario.done(scenario.node))

    [entry] = _answer_entries(scenario)
    record = _question(scenario)
    assert record is not None
    assert record.state is QuestionState.ANSWERED
    assert record.answered_by is AnsweredBy.ANSWERER
    assert record.answer == ANSWER
    assert record.cited_passages == ("P1",)
    assert record.check_verdict == "yes"
    assert record.source_commit
    assert record.passage_index and record.passage_index[0].id == "P1"
    assert record.answering_entry_id == entry.id
    assert entry.outcome is JournalOutcome.COMPLETED
    run_id = str(entry.parameters["run_id"])
    state = tmp_path / "home" / STUB_STATE_RELATIVE / f"{run_id}.json"
    assert state.is_file(), "the entry's run id is the run that was launched"
    [resume] = [json.loads(line) for line in argv_log.read_text().splitlines()]
    assert resume[resume.index("--instructions") + 1] == compose_instructions(
        QUESTION, ANSWER
    )
    assert scenario.status() is NodeStatus.DONE
    assert scenario.escalations() == []


def test_a_check_saying_no_declines_once_and_is_never_relaunched(
    scenario: Scenario,
) -> None:
    _script_answering(
        scenario,
        proposed_answer_reply(ANSWER, ["P1"]),
        check_reply("no", "P1 does not say that"),
    )

    scenario.tick_until("the question to be declined", lambda: _settled(scenario))
    for _ in range(5):
        scenario.tenant.tick(scenario.host)

    record = _question(scenario)
    assert record is not None
    assert record.state is QuestionState.DECLINED
    assert record.decline_reason is DeclineReason.CHECK_SAID_NO
    assert record.decline_detail == "P1 does not say that"
    assert len(_answer_entries(scenario)) == 1, "a decline is never relaunched"
    blocked = scenario.blocked()
    assert blocked is not None
    [row] = [
        row
        for row in _blocked_rows(scenario.store)
        if row["blocked_state_id"] == blocked.id
    ]
    assert row["question_state"] == "declined"
    assert row["decline_reason"] == "check_said_no"


def _blocked_rows(store: Store) -> list[Row]:
    request = ListingRequest(project_id=PROJECT, options={}, compact=False)
    return blocked_rows(store, request)


def test_an_answerer_decline_is_recorded_with_its_reason(
    scenario: Scenario,
) -> None:
    _script_answering(scenario, declining_answer_reply("the rules are silent"), None)

    scenario.tick_until("the question to be declined", lambda: _settled(scenario))

    record = _question(scenario)
    assert record is not None
    assert record.decline_reason is DeclineReason.ANSWERER_DECLINED
    assert record.decline_detail == "the rules are silent"


# --------------------------------------------------------------------------
# Races and recovery (D3, D4, D5, D9)
# --------------------------------------------------------------------------

LONG_RUN_SECONDS = "3.0"


def _question_exists(scenario: Scenario) -> bool:
    return _question(scenario) is not None


def _pm_answers(scenario: Scenario, text: str) -> None:
    record = _question(scenario)
    assert record is not None and record.blocked_state_id is not None
    resolve_block(scenario.store, record.blocked_state_id, "resume", text)


def _hold_the_stage(scenario: Scenario) -> dict[str, bool]:
    """Turn the answering stage into a no-op until ``held["on"]`` is cleared."""
    held = {"on": True}
    real_run = AnsweringStage.run

    def run(
        self: AnsweringStage, budget: TickBudget, faults: TickFaults
    ) -> StageResult:
        if held["on"]:
            return StageResult(False, False)
        return real_run(self, budget, faults)

    scenario.monkeypatch.setattr(AnsweringStage, "run", run)
    return held


def test_the_pm_answering_while_the_run_is_in_flight_wins_and_the_slice_finishes(
    scenario: Scenario,
) -> None:
    _script_answering(
        scenario,
        proposed_answer_reply(ANSWER, ["P1"]),
        check_reply("yes", "the rules say so"),
    )
    scenario.tick_until(
        "the slice run to be journaled", lambda: bool(scenario.entries())
    )
    scenario.monkeypatch.setenv(RUN_SECONDS_ENV, LONG_RUN_SECONDS)
    scenario.tick_until(
        "an answering run in flight", lambda: bool(_answer_entries(scenario))
    )

    _pm_answers(scenario, "The PM says: dev.")
    scenario.script(empty_reviews())
    scenario.tick_until("the slice to finish", lambda: scenario.done(scenario.node))

    [entry] = _answer_entries(scenario)
    assert not entry.is_resolved, "the node finished with the answering run in flight"
    assert scenario.escalations() == []
    scenario.tick_until(
        "the answering run to be finished",
        lambda: all(e.is_resolved for e in _answer_entries(scenario)),
    )
    record = _question(scenario)
    assert record is not None
    assert record.state is QuestionState.ANSWERED
    assert record.answered_by is AnsweredBy.PM
    assert record.answer == "The PM says: dev."
    [finished] = _answer_entries(scenario)
    assert finished.result is not None
    assert finished.result["question_outcome"] in (
        QuestionOutcome.DISCARDED.value,
        QuestionOutcome.BLOCK_RESOLVED.value,
    )


def test_a_pm_answer_before_the_launch_starts_no_run(scenario: Scenario) -> None:
    held = _hold_the_stage(scenario)
    scenario.tick_until(
        "the question to be recorded", lambda: _question_exists(scenario)
    )
    _pm_answers(scenario, "The PM says: dev.")
    held["on"] = False
    scenario.script(empty_reviews())

    scenario.tick_until("the slice to finish", lambda: scenario.done(scenario.node))

    record = _question(scenario)
    assert record is not None and record.answered_by is AnsweredBy.PM
    assert _answer_entries(scenario) == []


def test_a_pm_answer_between_the_read_and_the_journal_starts_no_run(
    scenario: Scenario,
) -> None:
    real_launch = stage_module.launch_answering
    answered = {"done": False}

    def racing(
        context: LaunchContext, record: QuestionRecord, budget: TickBudget
    ) -> LaunchStatus:
        if not answered["done"]:
            answered["done"] = True
            _pm_answers(scenario, "The PM says: dev.")
        return real_launch(context, record, budget)

    scenario.monkeypatch.setattr(stage_module, "launch_answering", racing)
    scenario.tick_until("the question to settle", lambda: _settled(scenario))

    record = _question(scenario)
    assert record is not None and record.answered_by is AnsweredBy.PM
    assert _answer_entries(scenario) == []


def test_a_restart_with_a_run_in_flight_adopts_it_without_a_second_launch(
    scenario: Scenario,
) -> None:
    _script_answering(
        scenario,
        proposed_answer_reply(ANSWER, ["P1"]),
        check_reply("yes", "the rules say so"),
    )
    scenario.tick_until(
        "the slice run to be journaled", lambda: bool(scenario.entries())
    )
    scenario.monkeypatch.setenv(RUN_SECONDS_ENV, "1.0")
    scenario.tick_until(
        "an answering run in flight", lambda: bool(_answer_entries(scenario))
    )

    # A restart: a new tenant knows no child handles, and recovery runs first.
    scenario._tenant = None  # pyright: ignore[reportPrivateUsage]
    reconcile(scenario.store, PROJECT, build_observer_registry(scenario.settings))
    [before] = _answer_entries(scenario)
    assert not before.is_resolved
    scenario.script(empty_reviews())
    scenario.tick_until("the question to be answered", lambda: _settled(scenario))

    record = _question(scenario)
    assert record is not None and record.answered_by is AnsweredBy.ANSWERER
    assert [e.id for e in _answer_entries(scenario)] == [before.id]


def test_a_crash_between_the_journal_and_the_spawn_declines_run_failed(
    scenario: Scenario,
) -> None:
    held = _hold_the_stage(scenario)
    scenario.tick_until(
        "the question to be recorded", lambda: _question_exists(scenario)
    )
    record = _question(scenario)
    assert record is not None
    # begin_answering commits; the process dies before it is spawned.
    scenario.store.begin_answering(
        record.id,
        AnsweringLaunch(
            node_id=record.node_id,
            run_id="amoeba-never-spawned-0001",
            parameters={
                "run_id": "amoeba-never-spawned-0001",
                "pipeline": "answering.yaml",
                "params": {},
                "scratch": str(scenario.tmp_path / "never-spawned"),
            },
            source_commit="abc123",
            passages=(),
            dropped_pm_answers=(),
        ),
    )
    time.sleep(GRACE_SECONDS + 0.2)

    reconcile(scenario.store, PROJECT, build_observer_registry(scenario.settings))
    held["on"] = False
    scenario.tick_until("the question to be declined", lambda: _settled(scenario))

    declined = _question(scenario)
    assert declined is not None
    assert declined.decline_reason is DeclineReason.ANSWERING_RUN_FAILED
    [entry] = _answer_entries(scenario)
    assert entry.outcome is JournalOutcome.NOT_APPLIED


def test_with_no_answerer_section_no_sq_answer_is_ever_journaled(
    tmp_path: Path, store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    plain = Scenario(tmp_path, store, monkeypatch)
    plain.script(agent_question_run(QUESTION), outcome="paused")

    plain.tick_until("the question to be settled", lambda: _settled(plain))

    record = _question(plain)
    assert record is not None
    assert record.decline_reason is DeclineReason.ANSWERER_NOT_CONFIGURED
    assert _answer_entries(plain) == []


# --------------------------------------------------------------------------
# The operator's view: the walkthrough's `amoeba inspect` steps (slice 144)
# --------------------------------------------------------------------------


def _inspect(scenario: Scenario, *arguments: str) -> list[dict[str, Any]]:
    """Run ``amoeba inspect <arguments> --json`` over a copy of the scenario's store."""
    supervisor = scenario.tmp_path / "cli" / "supervisor"
    supervisor.mkdir(parents=True, exist_ok=True)
    target = project_store_path(supervisor, PROJECT)
    with (
        sqlite3.connect(scenario.store.path) as source,
        sqlite3.connect(target) as copy,
    ):
        source.backup(copy)
    result = run_cli(
        ["inspect", *arguments, "--project", PROJECT, "--json"], supervisor
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_the_operator_sees_the_answered_question_through_inspect(
    scenario: Scenario,
) -> None:
    _script_answering(
        scenario, proposed_answer_reply(ANSWER, ["P1"]), check_reply("yes", "ok")
    )
    scenario.tick_until("the question to be answered", lambda: _settled(scenario))
    scenario.script(empty_reviews())
    scenario.tick_until("the slice to finish", lambda: scenario.done(scenario.node))

    journal = _inspect(scenario, "journal")
    [question] = _inspect(scenario, "questions")

    kinds = [row["kind"] for row in journal]
    assert kinds.count("sq_answer") == 1
    assert kinds.count("sq_run") >= 1
    assert question["state"] == "answered"
    assert question["answered_by"] == "answerer"
    assert question["check_verdict"] == "yes"
    assert question["cited_passages"] == ["P1"]
    assert question["passage_index"][0]["source"]
    assert question["answering_run_id"].startswith("amoeba-")


def test_the_operator_sees_a_declined_question_then_the_pm_answers_it(
    scenario: Scenario,
) -> None:
    _script_answering(
        scenario,
        proposed_answer_reply(ANSWER, ["P1"]),
        check_reply("no", "P1 does not say that"),
    )
    scenario.tick_until("the question to be declined", lambda: _settled(scenario))

    [block] = _inspect(scenario, "blocked")
    [declined] = _inspect(scenario, "questions")

    assert block["question_state"] == "declined"
    assert block["decline_reason"] == "check_said_no"
    assert declined["decline_detail"] == "P1 does not say that"
    assert declined["proposed_answer"] == ANSWER

    _pm_answers(scenario, "The PM says: dev.")
    scenario.script(empty_reviews())
    scenario.tick_until("the slice to finish", lambda: scenario.done(scenario.node))

    [answered] = _inspect(scenario, "questions")
    assert answered["state"] == "answered"
    assert answered["answered_by"] == "pm"
