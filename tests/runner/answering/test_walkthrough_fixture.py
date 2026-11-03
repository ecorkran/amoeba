"""143's assembly finds the walkthrough's scratch plan (slice 145, D6).

Needs no `sq` and no model. A rename that broke the naming-convention lookup would
otherwise show up only as a live decline.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from amoeba.runner.answering.passages import PassageSet
from amoeba.store import Store
from runner.answering.sources_assembly import assemble, settings, slice_node, snapshot
from runner.git_repo import commit_file, git

TREE = Path(__file__).parents[3] / "scripts" / "answerer_walkthrough" / "project"
INITIATIVE = 100
PLAN_FILES = (
    "000-concept.notes.md",
    "001-initiative-plan.notes.md",
    "100-arch.notes.md",
    "100-slices.notes.md",
)
MERGE_RULE = (
    "Slice branches merge to `main` automatically once their review passes; "
    "agents do not need to ask"
)


def _scratch_repo(path: Path) -> Path:
    """Commit every tree file at its relative path on ``main``, as the setup does."""
    path.mkdir()
    git(path, "init", "-q", "-b", "main")
    for number, file in enumerate(sorted(f for f in TREE.rglob("*") if f.is_file())):
        relative = file.relative_to(TREE).as_posix()
        stamp = f"2026-02-{number + 1:02d}T10:00:00+00:00"
        commit_file(path, relative, file.read_text(), f"add {relative}", date=stamp)
    return path


@pytest.mark.parametrize("index", [100, 101, 105])
def test_every_plan_file_and_case_passage_is_found(
    store: Store, tmp_path: Path, index: int
) -> None:
    repo = _scratch_repo(tmp_path / "checkout")
    node = slice_node(store, index, f"Slice {index}", INITIATIVE)

    result = assemble(
        store, node, snapshot(store, repo), settings=settings("CLAUDE.md")
    )

    assert isinstance(result, PassageSet)
    found = {Path(p.source).name for p in result.passages if p.source}
    assert found >= {*PLAN_FILES, "CLAUDE.md"}
    assert any("JSON Lines" in p.text for p in result.passages)
    assert any(MERGE_RULE in p.text for p in result.passages)
