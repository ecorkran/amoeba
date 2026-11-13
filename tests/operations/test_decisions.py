"""``decisions``: starts, narrowing, records, ``read_through`` (slice 224, 2.5)."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import pytest
from store.decision_support import (
    CORE,
    FIRST,
    LINT,
    SECOND,
    THIRD,
    TOOLS,
    TRADING,
    at,
    automatic_answer,
    seed_programs,
    waiting_then_pm,
)
from store.question_support import ANSWERING_RUN, claimed_question

from amoeba.answering.values import AnsweredBy, AnsweringEvidence, DeclineReason
from amoeba.operations.decisions import (
    DecisionsOutcome,
    DecisionsResult,
    decisions,
)
from amoeba.operations.decisions_models import AnswererBasis, PmBasis
from amoeba.operations.members import ContextForgeError
from amoeba.operations.reject_codes import RejectCode
from amoeba.store.answers import Settled, add_pm_answer, record_resume, settle_answered
from amoeba.store.decisions import advance_marker
from amoeba.store.models import QuestionKey
from amoeba.store.questions import insert_question
from amoeba.store.store import Store
from amoeba.store.vocabulary import Door, ResumeOutcome
from amoeba.upstream.context_forge.cli_call import CfCallFailed
from amoeba.upstream.context_forge.projects import ProjectNames
from operations.pause_support import DepsRig, build_deps

NAMES: ProjectNames = {CORE: "core-name", LINT: "lint-name"}


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    with Store.open(tmp_path / "amoeba.sqlite3") as opened:
        seed_programs(opened)
        yield opened


@pytest.fixture
def seqs(store: Store) -> list[int]:
    """Trading automatic, tools PM after waiting, trading automatic."""
    return [
        automatic_answer(store, FIRST, CORE, 1),
        waiting_then_pm(store, SECOND, LINT, 2),
        automatic_answer(store, THIRD, CORE, 3),
    ]


def _rig(
    tmp_path: Path, names: ProjectNames | CfCallFailed = NAMES
) -> tuple[DepsRig, list[int]]:
    calls: list[int] = []

    def read_names() -> ProjectNames | CfCallFailed:
        calls.append(1)
        return names

    rig = build_deps(tmp_path, polls={}, spawns=[])
    return replace(rig, deps=replace(rig.deps, project_names=read_names)), calls


def _run(store: Store, tmp_path: Path, document: object = None) -> DecisionsResult:
    rig, _calls = _rig(tmp_path)
    return decisions(store, {} if document is None else document, deps=rig.deps)


def test_the_default_start_is_after_the_marker(
    store: Store, tmp_path: Path, seqs: list[int]
) -> None:
    advance_marker(store, seqs[0])

    result = _run(store, tmp_path)

    assert result.outcome is DecisionsOutcome.LISTED
    assert [record.seq for record in result.records] == seqs[1:]
    assert result.marker == seqs[0]
    assert result.read_through == seqs[2]


def test_since_starts_at_a_time_and_gives_no_read_through(
    store: Store, tmp_path: Path, seqs: list[int]
) -> None:
    result = _run(store, tmp_path, {"since": at(2).isoformat()})

    assert [record.seq for record in result.records] == seqs[1:]
    assert result.read_through is None
    assert result.marker == 0


def test_program_narrows_the_listing_and_gives_no_read_through(
    store: Store, tmp_path: Path, seqs: list[int]
) -> None:
    result = _run(store, tmp_path, {"program": TOOLS})

    assert [record.seq for record in result.records] == [seqs[1]]
    assert {record.program for record in result.records} == {TOOLS}
    assert result.read_through is None


def test_an_empty_listing_has_no_read_through_and_asks_cf_nothing(
    store: Store, tmp_path: Path
) -> None:
    rig, calls = _rig(tmp_path, CfCallFailed("cf is down"))

    result = decisions(store, {}, deps=rig.deps)

    assert result.records == ()
    assert result.read_through is None
    assert result.marker == 0
    assert calls == []


def test_an_unknown_program_is_rejected_listing_the_known_ids(
    store: Store, tmp_path: Path
) -> None:
    result = _run(store, tmp_path, {"program": "nope"})

    assert result.outcome is DecisionsOutcome.REJECTED
    assert result.rejection is RejectCode.UNKNOWN_PROGRAM
    assert "tools, trading" in result.problems[0]
    assert result.marker is None


@pytest.mark.parametrize(
    "document", [{"since": "yesterday"}, {"since": "2026-11-10T12:00:00"}, {"x": 1}, 5]
)
def test_a_malformed_request_is_rejected(
    store: Store, tmp_path: Path, document: object
) -> None:
    result = _run(store, tmp_path, document)

    assert result.outcome is DecisionsOutcome.REJECTED
    assert result.rejection is RejectCode.MALFORMED
    assert result.problems


def test_an_automatic_record_names_its_passages_check_and_resume(
    store: Store, tmp_path: Path, seqs: list[int]
) -> None:
    result = _run(store, tmp_path)

    record = result.records[0]
    assert record.answered_by is AnsweredBy.ANSWERER
    assert record.member.id == CORE
    assert record.member.name == "core-name"
    assert record.program == TRADING
    assert record.run_id == FIRST.run_id
    assert record.paused_at == FIRST.paused_at
    assert record.slice_label == "223 pause-handling"
    assert record.prior_answer_seq is None
    assert isinstance(record.based_on, AnswererBasis)
    assert [passage.id for passage in record.based_on.cited] == ["r1"]
    assert record.based_on.cited[0].source == "CLAUDE.md"
    assert record.based_on.cited[0].kind is None
    assert record.based_on.check_verdict == "yes"
    assert record.based_on.check_reason == "cited"
    assert record.resume.outcome is None
    assert record.resume.detail is None


def test_a_resume_outcome_is_part_of_the_record(
    store: Store, tmp_path: Path, seqs: list[int]
) -> None:
    with store.write() as transaction:
        record_resume(
            transaction,
            seqs[0],
            ResumeOutcome.REFUSED,
            detail="run is busy",
            log=None,
            at=at(5),
        )

    record = _run(store, tmp_path).records[0]

    assert record.resume.outcome is ResumeOutcome.REFUSED
    assert record.resume.detail == "run is busy"
    assert record.resume.at == at(5)


def test_a_pm_record_after_a_waiting_question_carries_the_waiting_reason(
    store: Store, tmp_path: Path, seqs: list[int]
) -> None:
    record = _run(store, tmp_path).records[1]

    assert record.answered_by is AnsweredBy.PM
    assert record.member.name == "lint-name"
    assert record.based_on == PmBasis(
        waiting_reason=DeclineReason.ANSWER_LIMIT_REACHED, waiting_detail="limit 3"
    )


def test_a_pm_record_for_a_question_that_never_waited_has_no_basis(
    store: Store, tmp_path: Path
) -> None:
    key = QuestionKey("run-9", "2026-11-10T12:00:00+00:00")
    automatic_answer(store, key, CORE, 1)
    with store.write() as transaction:
        add_pm_answer(transaction, key, "pm override", now=at(2))

    first, second = _run(store, tmp_path).records

    assert isinstance(first.based_on, AnswererBasis)
    assert second.answered_by is AnsweredBy.PM
    assert second.based_on is None


def test_each_record_shows_the_door_that_carried_it_or_none(
    store: Store, tmp_path: Path
) -> None:
    key = QuestionKey("run-9", "2026-11-10T12:00:00+00:00")
    automatic_answer(store, key, CORE, 1)
    with store.write() as transaction:
        add_pm_answer(transaction, key, "by cli", now=at(2), via=Door.CLI)
        add_pm_answer(transaction, key, "by mcp", now=at(3), via=Door.MCP)
        # No door: how every answer from before migration 004 reads.
        add_pm_answer(transaction, key, "from before", now=at(4))

    records = _run(store, tmp_path).records

    assert [record.via for record in records] == [None, Door.CLI, Door.MCP, None]


def test_a_pm_override_shows_the_answer_it_replaced(
    store: Store, tmp_path: Path
) -> None:
    key = QuestionKey("run-9", "2026-11-10T12:00:00+00:00")
    automatic = automatic_answer(store, key, CORE, 1)
    with store.write() as transaction:
        add_pm_answer(transaction, key, "pm override", now=at(2))

    records = _run(store, tmp_path).records

    assert [record.prior_answer_seq for record in records] == [None, automatic]


def test_a_member_missing_from_the_names_is_a_context_forge_error(
    store: Store, tmp_path: Path, seqs: list[int]
) -> None:
    rig, _calls = _rig(tmp_path, {CORE: "core-name"})

    with pytest.raises(ContextForgeError, match=LINT):
        decisions(store, {}, deps=rig.deps)


def test_a_names_failure_raises_and_writes_nothing(
    store: Store, tmp_path: Path, seqs: list[int]
) -> None:
    rig, _calls = _rig(tmp_path, CfCallFailed("cf is down"))

    with pytest.raises(ContextForgeError, match="cf is down"):
        decisions(store, {}, deps=rig.deps)

    with store.read() as transaction:
        marker = transaction.execute("SELECT last_seen_seq FROM pm_marker").fetchone()
        count = transaction.execute("SELECT COUNT(*) FROM answers").fetchone()
    assert marker[0] == 0
    assert count[0] == len(seqs)


def test_citations_stored_as_written_are_matched_as_the_gate_read_them(
    store: Store, tmp_path: Path
) -> None:
    key = QuestionKey("run-8", "2026-11-10T12:00:00+00:00")
    with store.write() as transaction:
        insert_question(transaction, claimed_question(key, member_id=CORE), now=at(1))
    settled = settle_answered(
        store,
        key,
        ANSWERING_RUN,
        answer="auto",
        cited=(" r1 ", "", "R1"),
        evidence=AnsweringEvidence(verdict="yes", reason="cited"),
        gate=lambda _prior: None,
        now=at(1),
    )
    assert isinstance(settled, Settled)

    (record,) = _run(store, tmp_path).records

    assert isinstance(record.based_on, AnswererBasis)
    assert [passage.id for passage in record.based_on.cited] == ["r1"]
