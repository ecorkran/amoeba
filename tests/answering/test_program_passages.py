"""Program passages in assembly, no-slice reads and no-slice rendering
(slice 223, task 3.5; ported from slice 182's render and assemble tests)."""

from __future__ import annotations

import subprocess
from datetime import UTC, datetime

import pytest

from amoeba.answering.inputs import QuestionInput, render_question
from amoeba.answering.passages import (
    PassageKind,
    PassageSet,
    ProgramSources,
    SourceFile,
    SourcesProblem,
    assemble,
    render_passages,
)
from amoeba.answering.source_reads import (
    CommittedSources,
    SliceRef,
    SourceSelection,
    locate_sources,
    read_committed_sources,
)
from answering.sources_repo import SourcesRepo, build_sources_repo

DATE = datetime(2026, 11, 5, tzinfo=UTC)
CONCEPT = SourceFile(
    "docs/program-concept.md",
    PassageKind.PROGRAM_CONCEPT,
    DATE,
    "# Concept\nThe data project owns the feed.\n",
    member="trading-data",
)
MEMBER_LIST = SourceFile(
    "trading",
    PassageKind.PROGRAM_MEMBERS,
    DATE,
    "Program: trading\nProjects in this program:\n- trading-data\n",
    member=None,
)
RULES = SourceFile("CLAUDE.md", PassageKind.RULE, DATE, "# Rules\nUse main.\n", None)
PLAN = SourceFile("plan.md", PassageKind.PLAN, DATE, "plan\n", None)
NO_SLICE_LABEL = "none"


def _assemble(committed: tuple[SourceFile, ...], program: ProgramSources) -> PassageSet:
    result = assemble(
        committed,
        [],
        program_sources=program,
        max_chars=100_000,
        source_commit="c0ffee",
    )
    assert isinstance(result, PassageSet)
    return result


def test_both_program_kinds_are_emitted_after_rules_and_plan() -> None:
    result = _assemble((RULES, PLAN), ProgramSources(CONCEPT, MEMBER_LIST))

    assert [p.kind for p in result.passages] == [
        PassageKind.RULE,
        PassageKind.PLAN,
        PassageKind.PROGRAM_CONCEPT,
        PassageKind.PROGRAM_MEMBERS,
    ]


def test_the_concept_passage_names_its_member_and_path_and_the_list_has_no_source() -> (
    None
):
    rendered = render_passages(
        _assemble((RULES,), ProgramSources(CONCEPT, MEMBER_LIST))
    )

    assert (
        "kind: program_concept\nmember: trading-data\nsource: docs/program-concept.md"
        in rendered
    )
    members_section = rendered.split("kind: program_members")[1]
    assert "source:" not in members_section.split("\n\n")[0]
    assert "- trading-data" in members_section


def test_a_run_with_no_slice_has_rules_program_and_precedent_but_no_plan() -> None:
    result = _assemble((RULES,), ProgramSources(CONCEPT, MEMBER_LIST))

    kinds = {p.kind for p in result.passages}
    assert PassageKind.PLAN not in kinds
    assert {PassageKind.RULE, PassageKind.PROGRAM_MEMBERS} <= kinds


def test_a_program_with_no_concept_emits_the_member_list_and_no_concept() -> None:
    result = _assemble((RULES,), ProgramSources(None, MEMBER_LIST))

    assert [p.kind for p in result.passages] == [
        PassageKind.RULE,
        PassageKind.PROGRAM_MEMBERS,
    ]
    assert "program_concept" not in render_passages(result)


def test_program_text_counts_toward_the_size_limit() -> None:
    result = assemble(
        (RULES,),
        [],
        program_sources=ProgramSources(CONCEPT, MEMBER_LIST),
        max_chars=20,
        source_commit="c0ffee",
    )

    assert isinstance(result, SourcesProblem)
    assert "program" in result.detail


def test_the_program_files_are_the_concept_then_the_member_list() -> None:
    assert ProgramSources(CONCEPT, MEMBER_LIST).files == (CONCEPT, MEMBER_LIST)
    assert ProgramSources(None, MEMBER_LIST).files == (MEMBER_LIST,)


# No-slice source reads

RULES_ENTRIES = ("CLAUDE.md",)
SLICE = SliceRef(slice_index=132, initiative_index=120)
TIMEOUT = 8.0


@pytest.fixture(scope="module")
def sources(tmp_path_factory: pytest.TempPathFactory) -> SourcesRepo:
    return build_sources_repo(tmp_path_factory.mktemp("sources") / "repo")


def test_no_slice_ref_selects_no_plan_rows(sources: SourcesRepo) -> None:
    selection = locate_sources(
        sources.path, "main", None, RULES_ENTRIES, subprocess.run, TIMEOUT
    )

    assert isinstance(selection, SourceSelection)
    assert [file.kind for file in selection.files] == [PassageKind.RULE]


def test_a_slice_ref_still_selects_plan_rows(sources: SourcesRepo) -> None:
    selection = locate_sources(
        sources.path, "main", SLICE, RULES_ENTRIES, subprocess.run, TIMEOUT
    )

    assert isinstance(selection, SourceSelection)
    assert PassageKind.PLAN in [file.kind for file in selection.files]


def test_no_slice_reads_the_rules_alone(sources: SourcesRepo) -> None:
    committed = read_committed_sources(
        sources.path, "main", None, RULES_ENTRIES, 10_000_000, subprocess.run, TIMEOUT
    )

    assert isinstance(committed, CommittedSources)
    assert [file.path for file in committed.files] == ["CLAUDE.md"]
    assert all(file.member is None for file in committed.files)


# No-slice question rendering


def test_a_no_slice_question_renders_with_its_label() -> None:
    rendered = render_question(QuestionInput(NO_SLICE_LABEL, "Which limit?"))

    assert rendered == "# Question\n\nslice: none\n\nWhich limit?"


@pytest.mark.parametrize("label", ["", "   ", "\n"])
def test_a_blank_slice_label_is_still_rejected(label: str) -> None:
    with pytest.raises(ValueError, match="slice_label"):
        render_question(QuestionInput(label, "Which limit?"))
