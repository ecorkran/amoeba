"""Harness for the live slice-writing tests (slice 180, Task 9.3).

One run is one real ``sq run`` of the shipped pipeline from the scratch repo, with a
run I/O directory under the tier's temporary directory. Every run is checked against
the guarantees the pipeline makes (LLD D1, D4, D5) before a case looks at its reply.
"""

from __future__ import annotations

import fnmatch
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from live_harness import PipelineRun, watch_run
from live_request_settings import RequestLiveSettings

from amoeba.process import SQ_EXECUTABLE, RunOutcome, RunOutcomeDocument
from amoeba.runner.launch import mint_run_id
from amoeba.runner.request_run.inputs import RequestInput, prepare_request_directory
from amoeba.runner.request_run.pipeline_file import (
    COMMIT_PATHS,
    IO_DIRECTORY_OPTION,
    MAX_COST_OPTION,
    MODEL_PARAM,
    NEED_FILE,
    REPLY_FILE,
    REQUESTS_INDEX_PARAM,
    WRITE_PROMPT_FILE,
    slice_writing_pipeline_path,
)
from amoeba.runner.request_run.reply import (
    AlreadyMet,
    NewSlice,
    ReplyProblem,
    read_reply,
)
from live.request_run.scratch_repo import (
    REQUESTS_INDEX,
    TARGET_BRANCH,
    ScratchRepo,
    build_scratch_repo,
    cf_json,
    git,
)

SQ_RUN_TIMEOUT_SECONDS: Final = 900
#: How long a launcher gets to exit by itself once its run has an outcome.
LAUNCHER_EXIT_GRACE_SECONDS: Final = 60.0
ASKING_PROJECT_ID: Final = "scratch-asker"
ASKING_SLICE_LABEL: Final = "105 export-notes"
RUN_INPUT_OUTPUT_FILES: Final = frozenset({NEED_FILE, REPLY_FILE, WRITE_PROMPT_FILE})


@dataclass(frozen=True)
class RequestRun:
    """One finished run, checked: where it ran, what it left and what it replied."""

    repo: ScratchRepo
    io_directory: Path
    pipeline: PipelineRun
    start_commit: str
    new_commits: tuple[str, ...]
    reply: NewSlice | AlreadyMet | ReplyProblem

    def files_changed_by(self, commit: str) -> set[str]:
        """Repo-relative files one commit touched."""
        names = git(
            self.repo, "diff-tree", "--no-commit-id", "--name-only", "-r", commit
        )
        return {line for line in names.splitlines() if line}


def _plan_globs() -> tuple[str, ...]:
    """The two commit globs with the requests index filled in."""
    placeholder = "{" + REQUESTS_INDEX_PARAM + "}"
    return tuple(
        glob.replace(placeholder, str(REQUESTS_INDEX)) for glob in COMMIT_PATHS
    )


def launch_argv(run_id: str, io_directory: Path, model: str, cost: float) -> list[str]:
    """The slice design's launch contract (the process contract's final argv)."""
    return [
        SQ_EXECUTABLE,
        "run",
        str(slice_writing_pipeline_path()),
        str(REQUESTS_INDEX),
        "--run-id",
        run_id,
        IO_DIRECTORY_OPTION,
        str(io_directory),
        MAX_COST_OPTION,
        str(cost),
        "-p",
        f"{MODEL_PARAM}={model}",
    ]


@dataclass(frozen=True)
class RequestHarness:
    """Builds scratch repos and runs the pipeline in them."""

    parent: Path
    registry: Path
    environ: dict[str, str]
    settings: RequestLiveSettings

    def new_repo(self, name: str) -> ScratchRepo:
        directory = self.parent / name
        directory.mkdir()
        return build_scratch_repo(directory, self.registry, self.environ)

    def run(self, repo: ScratchRepo, name: str, need: str) -> RequestRun:
        """Run once in ``repo`` with ``need``; every-run checks raise on a breach."""
        io_directory = self.parent / f"{name}-io"
        io_directory.mkdir()
        request = RequestInput(
            asking_project_id=ASKING_PROJECT_ID,
            asking_slice_label=ASKING_SLICE_LABEL,
            requests_index=REQUESTS_INDEX,
            need=need,
        )
        prepare_request_directory(io_directory, request)
        start_commit = git(repo, "rev-parse", "HEAD")
        run_id = mint_run_id(datetime.now(UTC))
        argv = launch_argv(
            run_id,
            io_directory,
            self.settings.request_model,
            self.settings.max_cost_usd,
        )
        pipeline = watch_run(
            argv,
            run_id,
            repo.path,
            SQ_RUN_TIMEOUT_SECONDS,
            LAUNCHER_EXIT_GRACE_SECONDS,
            repo.environ,
        )
        new_commits = _check_every_run(repo, io_directory, pipeline, need, start_commit)
        return RequestRun(
            repo=repo,
            io_directory=io_directory,
            pipeline=pipeline,
            start_commit=start_commit,
            new_commits=new_commits,
            reply=read_reply(io_directory),
        )


def _check_every_run(
    repo: ScratchRepo,
    io_directory: Path,
    pipeline: PipelineRun,
    need: str,
    start_commit: str,
) -> tuple[str, ...]:
    """Assert what every run guarantees; return its new commits, oldest first."""
    report = f"{pipeline.poll}\n{pipeline.sq_output}"
    if pipeline.exit_code != 0:
        raise AssertionError(f"sq exited {pipeline.exit_code}: {pipeline.sq_output}")
    assert isinstance(pipeline.poll, RunOutcomeDocument), report
    assert pipeline.poll.outcome is RunOutcome.COMPLETED, report
    delivered = (io_directory / WRITE_PROMPT_FILE).read_text(encoding="utf-8")
    assert need in delivered, "write.prompt.md does not contain the need text"
    stray = [
        path.name
        for path in repo.path.rglob("*")
        if ".git" not in path.relative_to(repo.path).parts
        and path.name in RUN_INPUT_OUTPUT_FILES
    ]
    assert not stray, f"run I/O files in the checkout: {stray}"
    assert git(repo, "status", "--porcelain") == "", "the checkout is not clean"
    assert git(repo, "rev-parse", "--abbrev-ref", "HEAD") == TARGET_BRANCH
    commits = tuple(
        git(repo, "rev-list", "--reverse", f"{start_commit}..HEAD").splitlines()
    )
    assert len(commits) <= 1, f"more than one new commit: {commits}"
    for commit in commits:
        touched = git(
            repo, "diff-tree", "--no-commit-id", "--name-only", "-r", commit
        ).splitlines()
        outside = [
            name
            for name in touched
            if not any(fnmatch.fnmatchcase(name, glob) for glob in _plan_globs())
        ]
        assert not outside, (
            f"commit {commit} touched files outside the globs: {outside}"
        )
    initiatives = cf_json(repo, "list", "initiatives", "--json", "-a")
    assert isinstance(initiatives, list), json.dumps(initiatives)
    return commits
