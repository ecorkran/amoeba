"""A store, an asking checkout and a concept checkout for the ``gather`` tests."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from answering.sources_repo import build_sources_repo
from cf_plan_run import plan_cf_run
from git_repo import head_of

from amoeba.answering.passages import SourcesProblem
from amoeba.answering.settings import AnswererSettings
from amoeba.operations.pause_context import PauseContext, gather
from amoeba.store.models import Member, MemberSettings
from amoeba.store.programs import get_member, upsert_member, upsert_program
from amoeba.store.store import Store
from amoeba.upstream.squadron.run_file import ExecutionMode, RunFacts
from operations.program_rig import (
    ASKING_MEMBER,
    CONCEPT_MEMBER,
    CONCEPT_PATH,
    PROGRAM_ID,
    TIMEOUT,
    RoutedRun,
    build_concept_repo,
)

NOW = datetime(2026, 11, 10, 12, 0, tzinfo=UTC)
RULES_DIR = "project-documents/ai-project-guide/project-guides/rules"
#: In initiative 120's recorded plan, and the sources repo holds its design and tasks.
SLICE_PARAM = "132"
SLICE_LABEL = "132 Pipeline Supervisor"
UNUSED = TIMEOUT


def settings(*, max_chars: int = 1_000_000) -> AnswererSettings:
    return AnswererSettings(
        answer_limit=3,
        reserved_terms=(),
        rules_paths=("CLAUDE.md", f"{RULES_DIR}/*.md"),
        passages_max_chars=max_chars,
        answer_model="m",
        check_model="m",
        max_cost_usd=1.0,
    )


def facts(params: dict[str, str]) -> RunFacts:
    return RunFacts(
        params=params, execution_mode=ExecutionMode.SDK, working_directory=None
    )


@dataclass
class GatherRig:
    store: Store
    asker_repo: Path
    asker_head: str
    concept_repo: Path
    run: RoutedRun
    member: Member

    def gather(
        self, params: dict[str, str], *, max_chars: int = 1_000_000
    ) -> PauseContext | SourcesProblem:
        return gather(
            self.store,
            self.asker_repo,
            self.member,
            facts(params),
            settings(max_chars=max_chars),
            self.run,
        )


@contextmanager
def gather_rig(tmp_path: Path, *, with_concept: bool = True) -> Generator[GatherRig]:
    """A program of two members: the asker (the sources repo) and the concept holder."""
    asker = build_sources_repo(tmp_path / "asker").path
    concept_repo = tmp_path / "concept-repo"
    build_concept_repo(concept_repo)
    with Store.open(tmp_path / "amoeba.sqlite3") as store:
        with store.write() as transaction:
            upsert_program(
                transaction,
                program_id=PROGRAM_ID,
                concept_member=CONCEPT_MEMBER if with_concept else None,
                concept_path=CONCEPT_PATH if with_concept else None,
                now=NOW,
            )
            for project_id in (CONCEPT_MEMBER, ASKING_MEMBER):
                upsert_member(
                    transaction,
                    program_id=PROGRAM_ID,
                    settings=MemberSettings(
                        project_id=project_id,
                        rules_paths=("CLAUDE.md",),
                        authorize_allow=(),
                        authorize_deny=(),
                    ),
                    now=NOW,
                )
        with store.read() as transaction:
            member = get_member(transaction, ASKING_MEMBER)
        assert member is not None
        run = RoutedRun(
            concept_repo=concept_repo,
            target="main",
            project_known=True,
            fault=None,
            plan=plan_cf_run(integration_branch="", broken=False),
        )
        yield GatherRig(store, asker, head_of(asker), concept_repo, run, member)
