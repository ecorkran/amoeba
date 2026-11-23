"""The pause path gives ``cf -p`` a checkout's Context Forge id, never a member id
(slice 261, D6, 7.7).

The members here have ids Context Forge has never heard of, and their checkouts have
other ids. The stub ``cf`` fails any ``-p`` that is not a checkout's own id.
"""

from __future__ import annotations

import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from store.seed import insert_checkout

from amoeba.answering.passages import PassageKind, SourcesProblem, SourcesProblemKind
from amoeba.operations.pause_context import PauseContext
from operations.gather_rig import NOW, SLICE_PARAM, GatherRig, gather_rig
from operations.program_rig import (
    ASKER_CF_ID,
    CONCEPT_CF_ID,
    CONCEPT_MEMBER,
    RoutedRun,
)

SECOND_CONCEPT_CF_ID = "cf-id-of-a-second-concept-checkout"


class OnlyCheckoutIds:
    """Wraps the rig's ``cf`` and ``git``: a ``cf`` call that names a project with
    ``-p`` fails unless the id is one of ``allowed``."""

    def __init__(self, inner: RoutedRun, allowed: set[str]) -> None:
        self.inner = inner
        self.allowed = allowed
        self.project_ids: list[str] = []

    def __call__(
        self, argv: Sequence[str], **kwargs: Any
    ) -> subprocess.CompletedProcess[str]:
        if argv[0] == "cf" and "-p" in argv:
            project_id = argv[list(argv).index("-p") + 1]
            self.project_ids.append(project_id)
            if project_id not in self.allowed:
                return subprocess.CompletedProcess(
                    list(argv), 1, "", f"Project {project_id} not found"
                )
        return self.inner(argv, **kwargs)


def _gather(rig: GatherRig, run: OnlyCheckoutIds) -> PauseContext | SourcesProblem:
    rig.run = run  # type: ignore[assignment]
    return rig.gather({"slice": SLICE_PARAM})


def test_the_plan_the_target_and_the_concept_are_read_with_checkout_ids(
    tmp_path: Path,
) -> None:
    with gather_rig(tmp_path) as rig:
        run = OnlyCheckoutIds(rig.run, {ASKER_CF_ID, CONCEPT_CF_ID})

        context = _gather(rig, run)

    assert isinstance(context, PauseContext), context
    kinds = {passage.kind for passage in context.passages.passages}
    assert {PassageKind.PLAN, PassageKind.PROGRAM_CONCEPT} <= kinds
    assert set(run.project_ids) == {ASKER_CF_ID, CONCEPT_CF_ID}


def test_of_two_concept_checkouts_here_the_one_added_first_is_read(
    tmp_path: Path,
) -> None:
    with gather_rig(tmp_path) as rig:
        with rig.store.write() as transaction:
            insert_checkout(
                transaction,
                member_id=CONCEPT_MEMBER,
                cf_project_id=SECOND_CONCEPT_CF_ID,
                path=str(tmp_path / "second-clone"),
                now=NOW.replace(year=2030),
            )
        run = OnlyCheckoutIds(rig.run, {ASKER_CF_ID, CONCEPT_CF_ID})

        context = _gather(rig, run)

    assert isinstance(context, PauseContext), context
    assert SECOND_CONCEPT_CF_ID not in run.project_ids


def test_a_concept_member_with_no_checkout_here_is_a_missing_problem(
    tmp_path: Path,
) -> None:
    with gather_rig(tmp_path) as rig:
        with rig.store.write() as transaction:
            transaction.execute(
                "DELETE FROM checkouts WHERE member_id = ?", (CONCEPT_MEMBER,)
            )
        run = OnlyCheckoutIds(rig.run, {ASKER_CF_ID})

        problem = _gather(rig, run)

    assert isinstance(problem, SourcesProblem)
    assert problem.kind is SourcesProblemKind.MISSING
    assert "no checkout on this machine" in problem.detail


def test_a_cf_id_that_is_not_a_checkout_id_fails_the_read(tmp_path: Path) -> None:
    """The stub really refuses: the member id given to ``-p`` would fail."""
    with gather_rig(tmp_path) as rig:
        run = OnlyCheckoutIds(rig.run, set())

        problem = _gather(rig, run)

    assert isinstance(problem, SourcesProblem)
