"""``runs`` document values for the ``status`` tests (slice 261, D11): a recorded
listing entry turned into the document's run, with the lookup and reads a test gives."""

from __future__ import annotations

from amoeba.operations.runs_document import (
    CallLine,
    CompletedRun,
    LookupKind,
    OpenRun,
    RunCheckpoint,
    RunFileFacts,
    RunLookup,
    RunsDocument,
)
from amoeba.upstream.squadron.run_list import ListedRun


def project(project_id: str) -> RunLookup:
    return RunLookup(kind=LookupKind.PROJECT, project_id=project_id)


def not_a_project(message: str = "none") -> RunLookup:
    return RunLookup(kind=LookupKind.NOT_A_PROJECT, detail=message)


def failed(detail: str) -> RunLookup:
    return RunLookup(kind=LookupKind.FAILED, detail=detail)


def open_run(  # noqa: PLR0913 - what a document run can hold, each optional
    listed: ListedRun,
    lookup: RunLookup | None = None,
    *,
    run_file: RunFileFacts | None = None,
    run_file_problem: str | None = None,
    last_call: CallLine | None = None,
) -> OpenRun:
    """``listed`` as the document holds it. With no ``lookup`` the run's directory
    decides: none is ``no_directory``, any other is that project's lookup the test must
    give, so a test that places a run always passes one."""
    directory = listed.working_directory
    if lookup is None:
        if directory is not None:
            raise ValueError("a run with a directory needs the lookup the test means")
        lookup = RunLookup(kind=LookupKind.NO_DIRECTORY)
    checkpoint = listed.checkpoint
    return OpenRun(
        run_id=listed.run_id,
        pipeline=listed.pipeline,
        status=listed.status,
        working_directory=None if directory is None else str(directory),
        checkpoint=None
        if checkpoint is None
        else RunCheckpoint(
            kind=checkpoint.kind,
            paused_at=checkpoint.paused_at,
            question=checkpoint.question,
        ),
        lookup=lookup,
        run_file=run_file,
        run_file_problem=run_file_problem,
        last_call=last_call,
    )


def document_of(*runs: ListedRun, lookup: RunLookup | None = None) -> RunsDocument:
    """A document holding ``runs``: completed ones as ids and statuses, the rest open
    with ``lookup`` (``no_directory`` for a run with no directory)."""
    return RunsDocument(
        open_runs=tuple(
            open_run(run, lookup if run.working_directory is not None else None)
            for run in runs
            if not run.is_completed
        ),
        completed_runs=tuple(
            CompletedRun(run_id=run.run_id, status=run.status)
            for run in runs
            if run.is_completed
        ),
    )
