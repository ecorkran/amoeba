"""``gather``: slice, rules and plan, program passages and precedent in one context
(slice 223, task 4.7). ``git`` is real; ``cf`` is replayed from recordings."""

from __future__ import annotations

import subprocess
from contextlib import AbstractContextManager
from pathlib import Path

import pytest
from store.question_support import KEY

from amoeba.answering.launch import passage_refs
from amoeba.answering.passages import (
    PassageKind,
    SourcesProblem,
    SourcesProblemKind,
)
from amoeba.answering.values import AnsweringEvidence, DeclineReason
from amoeba.operations.pause_context import NO_SLICE_LABEL, PauseContext, gather
from amoeba.store.answers import add_pm_answer, settle_answered
from amoeba.store.models import QuestionKey
from amoeba.store.programs import upsert_program
from amoeba.store.questions import NewQuestion, insert_question
from amoeba.store.standing import give_standing, withdraw_standing
from amoeba.store.store import Store, Transaction
from amoeba.store.vocabulary import StandingReach
from operations.gather_rig import (
    ASKER_CF_ID,
    NOW,
    SLICE_LABEL,
    SLICE_PARAM,
    facts,
    gather_rig,
    settings,
)
from operations.program_rig import (
    ASKING_MEMBER,
    CONCEPT_MEMBER,
    CONCEPT_PATH,
    PROGRAM_ID,
)


def _context(result: PauseContext | SourcesProblem) -> PauseContext:
    assert isinstance(result, PauseContext), result
    return result


def _kinds(context: PauseContext) -> list[PassageKind]:
    return [passage.kind for passage in context.passages.passages]


def _question(key: QuestionKey, *, claimed: bool) -> NewQuestion:
    return NewQuestion(
        key=key,
        member_id=ASKING_MEMBER,
        question="Which branch do we merge to?",
        checkout="/work/asker",
        slice_label=SLICE_LABEL,
        source_commit=None,
        passages=None,
        answering_run_id="a-1" if claimed else None,
        waiting_reason=None if claimed else DeclineReason.NO_ANSWER_ON_FILE,
        waiting_detail=None,
    )


def test_a_full_context_with_a_slice(tmp_path: Path) -> None:
    with gather_rig(tmp_path) as rig:
        context = _context(rig.gather({"slice": SLICE_PARAM}))

    assert context.slice_label == SLICE_LABEL
    assert context.source_commit == rig.asker_head
    kinds = set(_kinds(context))
    assert kinds == {
        PassageKind.RULE,
        PassageKind.PLAN,
        PassageKind.PROGRAM_CONCEPT,
        PassageKind.PROGRAM_MEMBERS,
    }
    assert context.refs == passage_refs(context.passages)
    assert "kind: program_concept\nmember: trading-data" in context.passages_markdown
    assert context.passages_markdown.startswith("## Passage P1")


def test_a_no_slice_context_has_no_plan_passages(tmp_path: Path) -> None:
    with gather_rig(tmp_path) as rig:
        context = _context(rig.gather({}))

    assert context.slice_label == NO_SLICE_LABEL
    kinds = set(_kinds(context))
    assert PassageKind.PLAN not in kinds
    assert {
        PassageKind.RULE,
        PassageKind.PROGRAM_CONCEPT,
        PassageKind.PROGRAM_MEMBERS,
    } <= kinds


def test_a_program_with_no_concept_still_gets_the_member_list(tmp_path: Path) -> None:
    with gather_rig(tmp_path, with_concept=False) as rig:
        context = _context(rig.gather({}))

    kinds = _kinds(context)
    assert PassageKind.PROGRAM_CONCEPT not in kinds
    assert kinds[-1] is PassageKind.PROGRAM_MEMBERS


def test_pm_precedent_appears_after_a_pm_answer_and_not_for_automatic_answers(
    tmp_path: Path,
) -> None:
    other = QuestionKey("run-0", "2026-11-10T08:00:00+00:00")
    with gather_rig(tmp_path) as rig:
        with rig.store.write() as transaction:
            insert_question(transaction, _question(KEY, claimed=True), now=NOW)
            insert_question(transaction, _question(other, claimed=False), now=NOW)
            add_pm_answer(transaction, other, "Merge to main.", now=NOW, via=None)
        settle_answered(
            rig.store,
            KEY,
            "a-1",
            answer="automatic text",
            cited=(),
            evidence=AnsweringEvidence(),
            gate=lambda _prior: None,
            now=NOW,
        )
        context = _context(rig.gather({"slice": SLICE_PARAM}))

    answers = [p for p in context.passages.passages if p.kind is PassageKind.PM_ANSWER]
    assert [p.text for p in answers] == ["Merge to main."]
    assert answers[0].slice_label == SLICE_LABEL
    assert answers[0].question_id == "run-0@2026-11-10T08:00:00+00:00"
    assert "automatic text" not in context.passages_markdown


def test_a_pm_answer_with_no_recorded_slice_renders_with_no_slice_line(
    tmp_path: Path,
) -> None:
    key = QuestionKey("run-9", "2026-11-10T09:00:00+00:00")
    with gather_rig(tmp_path) as rig:
        waiting = NewQuestion(
            key=key,
            member_id=ASKING_MEMBER,
            question="Limit reached before context?",
            checkout="/work/asker",
            slice_label=None,
            source_commit=None,
            passages=None,
            answering_run_id=None,
            waiting_reason=DeclineReason.NO_ANSWER_ON_FILE,
            waiting_detail=None,
        )
        with rig.store.write() as transaction:
            insert_question(transaction, waiting, now=NOW)
            add_pm_answer(transaction, key, "Use main.", now=NOW, via=None)
        context = _context(rig.gather({}))

    answers = [p for p in context.passages.passages if p.kind is PassageKind.PM_ANSWER]
    assert len(answers) == 1
    assert answers[0].slice_label is None
    assert "slice:" not in context.passages_markdown.split("kind: pm_answer")[1]


@pytest.mark.parametrize(
    ("params", "kind"),
    [
        ({"slice": "not-a-number"}, SourcesProblemKind.MISSING),
        ({"slice": "299"}, SourcesProblemKind.MISSING),
    ],
)
def test_a_slice_problem_is_returned_and_nothing_partial(
    tmp_path: Path, params: dict[str, str], kind: SourcesProblemKind
) -> None:
    with gather_rig(tmp_path) as rig:
        result = rig.gather(params)

    assert isinstance(result, SourcesProblem)
    assert result.kind is kind
    assert not rig.run.git_calls


def test_a_failing_cf_config_get_is_sources_unreadable_with_the_output_head(
    tmp_path: Path,
) -> None:
    with gather_rig(tmp_path) as rig:
        rig.run.fault = lambda argv: (
            subprocess.CompletedProcess(list(argv), 1, "cf config broke", "")
            if argv[1] == "config"
            else None
        )
        result = rig.gather({})

    assert isinstance(result, SourcesProblem)
    assert result.kind is SourcesProblemKind.UNREADABLE
    assert "cf config broke" in result.detail
    assert not rig.run.git_calls


def test_an_empty_integration_branch_reads_the_default_target_and_a_set_one_is_used(
    tmp_path: Path,
) -> None:
    with gather_rig(tmp_path) as rig:
        rig.run.target = ""
        default = _context(rig.gather({}))
        rig.run.target = "no-such-branch"
        missing_branch = rig.gather({})

    assert default.source_commit == rig.asker_head
    assert isinstance(missing_branch, SourcesProblem)
    assert missing_branch.kind is SourcesProblemKind.UNREADABLE
    assert "no-such-branch" in " ".join(" ".join(c) for c in rig.run.git_calls)


def test_a_missing_concept_file_is_the_programs_problem_and_nothing_is_assembled(
    tmp_path: Path,
) -> None:
    with gather_rig(tmp_path) as rig:
        rig.run.fault = lambda argv: (
            subprocess.CompletedProcess(list(argv), 128, "", "fatal: nope")
            if "show" in argv and argv[-1].endswith(f":{CONCEPT_PATH}")
            else None
        )
        result = rig.gather({})

    assert isinstance(result, SourcesProblem)
    assert CONCEPT_MEMBER in result.detail


def test_over_the_limit_is_sources_too_large(tmp_path: Path) -> None:
    with gather_rig(tmp_path) as rig:
        result = rig.gather({}, max_chars=2_000)

    assert isinstance(result, SourcesProblem)
    assert result.kind is SourcesProblemKind.TOO_LARGE


# Standing answers (slice 230, D5)


def _give(
    store: Store,
    text: str,
    reach: StandingReach = StandingReach.ALL,
    program_id: str | None = None,
    member_id: str | None = None,
) -> int:
    with store.write() as transaction:
        standing_id, _ = give_standing(
            transaction, text, reach, program_id, member_id, NOW
        )
    return standing_id


def _standing_sources(context: PauseContext) -> list[str | None]:
    return [
        passage.source
        for passage in context.passages.passages
        if passage.kind is PassageKind.STANDING_ANSWER
    ]


def test_a_member_with_no_pm_answers_is_sent_an_all_reach_row(tmp_path: Path) -> None:
    with gather_rig(tmp_path) as rig:
        standing_id = _give(rig.store, "Fixture versions are never bumped.")
        context = _context(rig.gather({}))

    assert _standing_sources(context) == [f"standing:{standing_id}"]
    assert PassageKind.PM_ANSWER not in _kinds(context)
    assert "kind: standing_answer" in context.passages_markdown


def test_only_rows_in_reach_and_active_are_sent(tmp_path: Path) -> None:
    with gather_rig(tmp_path) as rig:
        with rig.store.write() as transaction:
            upsert_program(
                transaction,
                program_id="elsewhere",
                concept_member=None,
                concept_path=None,
                now=NOW,
            )
        mine = _give(rig.store, "program", StandingReach.PROGRAM, PROGRAM_ID)
        _give(rig.store, "other program", StandingReach.PROGRAM, "elsewhere")
        _give(rig.store, "other member", StandingReach.MEMBER, None, CONCEPT_MEMBER)
        me = _give(rig.store, "member", StandingReach.MEMBER, None, ASKING_MEMBER)
        gone = _give(rig.store, "withdrawn")
        with rig.store.write() as transaction:
            withdraw_standing(transaction, gone, "old", NOW)
        context = _context(rig.gather({}))

    assert _standing_sources(context) == [f"standing:{mine}", f"standing:{me}"]


def test_with_no_rows_the_passages_are_as_before(tmp_path: Path) -> None:
    with gather_rig(tmp_path) as rig:
        before = _context(rig.gather({}))
        gone = _give(rig.store, "withdrawn")
        with rig.store.write() as transaction:
            withdraw_standing(transaction, gone, "old", NOW)
        after = _context(rig.gather({}))

    assert after.passages_markdown == before.passages_markdown
    assert after.refs == before.refs


def test_pause_sources_reads_the_store_once_and_the_gather_reads_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with gather_rig(tmp_path) as rig:
        _give(rig.store, "ruling")
        entries: list[None] = []
        original = Store.read

        def counting(store: Store) -> AbstractContextManager[Transaction]:
            entries.append(None)
            return original(store)

        sources = rig.sources()
        monkeypatch.setattr(Store, "read", counting)
        monkeypatch.setattr(Store, "write", counting)
        context = gather(
            sources,
            rig.asker_repo,
            rig.member,
            facts({}),
            settings(),
            rig.run,
            cf_project_id=ASKER_CF_ID,
        )

    assert isinstance(context, PauseContext)
    assert entries == []


def test_standing_answers_that_tip_the_cap_give_both_shares(tmp_path: Path) -> None:
    with gather_rig(tmp_path) as rig:
        base = len(_context(rig.gather({})).passages_markdown)
        _give(rig.store, "x" * 500)
        result = rig.gather({}, max_chars=base + 100)

    assert isinstance(result, SourcesProblem)
    assert result.kind is SourcesProblemKind.TOO_LARGE
    assert f"are {base} characters and standing answers " in result.detail
    assert f"the limit is {base + 100}" in result.detail
