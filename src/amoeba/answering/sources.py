"""The one call the answering run makes to get its passages (slice 143, 144's input).

``assemble_sources`` reads the target of the caller's checkout, reads the committed
rules and plan (``source_reads``), and hands all of it, with the PM precedent the
caller passes in, to the pure ``assemble``. It writes nothing. A problem the
repository or the configuration can cause is returned as a value.
"""

from __future__ import annotations

from pathlib import Path

from amoeba.answering.passages import (
    PassageSet,
    PmAnswer,
    SourcesProblem,
    assemble,
    unreadable,
)
from amoeba.answering.settings import AnswererSettings
from amoeba.answering.source_reads import (
    CommittedSources,
    SliceRef,
    read_committed_sources,
)
from amoeba.upstream.context_forge.cli_call import CfRun
from amoeba.upstream.context_forge.target_read import ReadFailure, read_target


def assemble_sources(
    checkout: Path,
    cf_project_id: str,
    slice_ref: SliceRef,
    slice_label: str,
    pm_precedent: tuple[PmAnswer, ...],
    settings: AnswererSettings,
    run: CfRun,
    timeout_seconds: float,
) -> PassageSet | SourcesProblem:
    """The passages for one question: a set, or a named problem.

    Args:
        checkout: The repository checkout the question was asked in.
        cf_project_id: The Context Forge project of that checkout.
        slice_ref: The slice and its initiative, as Context Forge indexes them.
        slice_label: ``"<index> <title>"``; PM answers on the same slice come first.
        pm_precedent: Every earlier PM answer offered as precedent.
        settings: The answerer's settings.
        run: Runs ``cf`` and ``git``.
        timeout_seconds: The longest one call may run.

    A problem is final: the caller declines the question.
    """
    target = read_target(checkout, cf_project_id, run, timeout_seconds)
    if isinstance(target, ReadFailure):
        return unreadable(target.detail)
    committed = read_committed_sources(
        checkout,
        target,
        slice_ref,
        settings.rules_paths,
        settings.passages_max_chars,
        run,
        timeout_seconds,
    )
    if not isinstance(committed, CommittedSources):
        return committed
    return assemble(
        committed.files,
        pm_precedent,
        question_slice_label=slice_label,
        max_chars=settings.passages_max_chars,
        source_commit=committed.commit,
    )
