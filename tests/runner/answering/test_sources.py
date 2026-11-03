"""``assemble_sources``, PM precedent and slice labels (slice 143, D3/D6/D9)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from question_harness import PROJECT, seed_question

from amoeba.runner.answering.passages import (
    PassageKind,
    PassageSet,
    SourcesProblem,
    SourcesProblemKind,
    render_passages,
)
from amoeba.runner.answering.sources import (
    pm_precedent,
    slice_label,
)
from amoeba.store import (
    AnsweredBy,
    NodeKind,
    QuestionRecord,
    QuestionState,
    Store,
)
from runner.answering.sources_assembly import assemble as _assemble
from runner.answering.sources_assembly import node as _node
from runner.answering.sources_assembly import run as _run
from runner.answering.sources_assembly import settings as _settings
from runner.answering.sources_assembly import slice_node as _slice
from runner.answering.sources_assembly import snapshot as _snapshot
from runner.answering.sources_repo import (
    CountingBudget,
    build_sources_repo,
)
from runner.git_repo import commit_file, git

RULES_DIR = "project-documents/ai-project-guide/project-guides/rules"
EXPECTED = Path(__file__).parent / "fixtures" / "expected_end_to_end.md"


def _pm_answer(
    store: Store, node_id: str, question: str | None, answer: str | None, day: int
) -> QuestionRecord:
    return seed_question(
        store,
        node_id,
        state=QuestionState.ANSWERED,
        answered_by=AnsweredBy.PM,
        question=question,
        answer=answer,
        updated_at=datetime(2026, 3, day, 12, 0, tzinfo=UTC),
    )


# Precedent (D6)


def test_only_pm_answers_with_text_and_a_question_are_precedent(store: Store) -> None:
    node = _slice(store)
    kept = _pm_answer(store, node.id, "Which branch?", "Use main.", 1)
    _pm_answer(store, node.id, "Blank answer?", "   ", 2)
    _pm_answer(store, node.id, "No answer?", None, 3)
    _pm_answer(store, node.id, None, "No question.", 4)
    _pm_answer(store, node.id, "   ", "Blank question.", 5)
    seed_question(
        store,
        node.id,
        state=QuestionState.ANSWERED,
        answered_by=AnsweredBy.ANSWERER,
        question="By the answerer?",
        answer="Yes.",
    )
    seed_question(store, node.id, question="Still pending?")

    precedent = pm_precedent(store, PROJECT)

    assert len(precedent) == 1
    assert precedent[0].record_id == kept.id
    assert precedent[0].question == "Which branch?"
    assert precedent[0].answer == "Use main."
    assert precedent[0].slice_label == "132 Demo Slice"
    assert precedent[0].node_id == node.id
    assert precedent[0].date == datetime(2026, 3, 1, 12, 0, tzinfo=UTC)


def test_slice_label_is_the_index_then_the_title(store: Store) -> None:
    assert slice_label(_slice(store, 143, "Source Passages")) == "143 Source Passages"


def test_slice_label_without_an_index_is_a_programming_error(store: Store) -> None:
    node = _node(store, NodeKind.SLICE, "Unindexed", None, None)

    with pytest.raises(ValueError, match="no Context Forge index"):
        slice_label(node)


# The slice's place in the tree (D1)


def test_a_slice_without_a_parent_raises(store: Store) -> None:
    node = _node(store, NodeKind.SLICE, "Orphan", 132, None)

    with pytest.raises(ValueError, match="no initiative parent"):
        _assemble(store, node, None)


def test_a_slice_under_a_non_initiative_parent_raises(store: Store) -> None:
    parent = _node(store, NodeKind.PHASE_OR_ARTIFACT, "Phase", 120, None)
    node = _node(store, NodeKind.SLICE, "Child", 132, parent.id)

    with pytest.raises(ValueError, match="no initiative parent"):
        _assemble(store, node, None)


def test_an_initiative_without_an_index_raises(store: Store) -> None:
    parent = _node(store, NodeKind.INITIATIVE, "Initiative", None, None)
    node = _node(store, NodeKind.SLICE, "Child", 132, parent.id)

    with pytest.raises(ValueError, match="no Context Forge index"):
        _assemble(store, node, None)


# Problems and budget refusals (D9)


def test_no_snapshot_is_unreadable_with_the_reason(store: Store) -> None:
    result = _assemble(store, _slice(store), None)

    assert isinstance(result, SourcesProblem)
    assert result.kind is SourcesProblemKind.UNREADABLE
    assert "no observed snapshot" in result.detail


def test_a_failed_target_read_is_unreadable_with_the_detail(
    store: Store, tmp_path: Path
) -> None:
    snapshot = _snapshot(store, build_sources_repo(tmp_path / "repo").path)

    result = _assemble(store, _slice(store), snapshot, run=_run(cf_exit=1))

    assert isinstance(result, SourcesProblem)
    assert result.kind is SourcesProblemKind.UNREADABLE
    assert "config get" in result.detail


@pytest.mark.parametrize("allowed", [0, 1, 2])
def test_a_budget_refusal_at_each_step_gives_none(
    store: Store, tmp_path: Path, allowed: int
) -> None:
    snapshot = _snapshot(store, build_sources_repo(tmp_path / "repo").path)

    result = _assemble(
        store, _slice(store), snapshot, budget=CountingBudget(allowed=allowed)
    )

    assert result is None


# End to end


def _small_repo(path: Path) -> Path:
    path.mkdir()
    git(path, "init", "-q", "-b", "main")
    files = [
        ("CLAUDE.md", "# Rules\nUse main.\n"),
        ("rules/a.md", "# A\nalpha\n"),
        ("rules/b.md", "# B\nbeta\n"),
        ("project-documents/user/architecture/120-slices.demo.md", "# Slices\nplan\n"),
        (
            "project-documents/user/slices/132-slice.demo.md",
            "# Design\nbody\n## Detail\nmore\n",
        ),
    ]
    for day, (name, text) in enumerate(files, start=1):
        stamp = f"2026-02-{day:02d}T10:00:00+02:00"
        commit_file(path, name, text, f"add {name}", date=stamp)
    return path


def test_assembly_and_rendering_equal_the_hand_written_file(
    store: Store, tmp_path: Path
) -> None:
    repo = _small_repo(tmp_path / "repo")
    node = _slice(store)
    other = _slice(store, 133, "Other Slice")
    _pm_answer(store, other.id, "Release how?", "Tag it.", 2)
    _pm_answer(store, node.id, "Which branch?", "Use main.", 1)
    settings = _settings("CLAUDE.md", "rules/*.md")

    result = _assemble(
        store, node, _snapshot(store, repo), settings=settings, run=_run("main")
    )

    assert isinstance(result, PassageSet)
    assert render_passages(result) == EXPECTED.read_text()
    assert result.dropped_pm_answers == ()


def test_the_fixture_repository_gives_the_planned_order(
    store: Store, tmp_path: Path
) -> None:
    repo = build_sources_repo(tmp_path / "repo")
    settings = _settings("CLAUDE.md", f"{RULES_DIR}/*.md")

    result = _assemble(
        store, _slice(store), _snapshot(store, repo.path), settings=settings
    )

    assert isinstance(result, PassageSet)
    assert [p.id for p in result.passages] == [
        f"P{n}" for n in range(1, len(result.passages) + 1)
    ]
    sources = list(dict.fromkeys(p.source for p in result.passages))
    assert [s.rsplit("/", 1)[-1] for s in sources if s] == [
        "CLAUDE.md",
        "git.md",
        "python.md",
        "000-concept.amoeba.md",
        "001-initiative-plan.amoeba.md",
        "120-arch.runner-routing-engine.md",
        "120-slices.runner-routing-engine.md",
        "132-slice.pipeline-supervisor.md",
        "132-tasks.pipeline-supervisor.md",
    ]
    assert result.passages[0].kind is PassageKind.RULE
    assert result.passages[0].date == repo.dates["CLAUDE.md"]
    assert result.source_commit == git(repo.path, "rev-parse", "HEAD").stdout.strip()
