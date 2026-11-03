"""Launch an answering run for one pending question (D6, D8, D10).

Everything that can fail cleanly happens before the journal entry: the sources, the
scratch directory and the command line. Then ``begin_answering`` journals the entry
and moves the record in one transaction, and the process is started from the
scratch directory with no checkout lookup, branch check or hold. Every launch-path
failure declines ``answering_launch_failed`` and nothing retries.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Final

from amoeba.runner.answering.decide import sources_reason
from amoeba.runner.answering.finish import finish_answering
from amoeba.runner.answering.inputs import QuestionInput, prepare_scratch
from amoeba.runner.answering.passages import PassageSet, SourcesProblem, render_passages
from amoeba.runner.answering.pipeline_file import (
    ANSWER_MODEL_PARAM,
    CHECK_MODEL_PARAM,
    answering_pipeline_path,
)
from amoeba.runner.answering.sources import assemble_sources, slice_label
from amoeba.runner.budget import TickBudget
from amoeba.runner.cf_call import CfRun
from amoeba.runner.faults import LaunchFailure
from amoeba.runner.ingest.outcome import cut_to_bound
from amoeba.runner.launch import (
    PARAM_PARAMS,
    PARAM_PIPELINE,
    LaunchError,
    LaunchTracker,
    PopenFactory,
    build_argv,
    log_paths,
    mint_run_id,
    spawn,
)
from amoeba.runner.observed import LaunchFailed
from amoeba.runner.project_config import AnswererSettings
from amoeba.store import (
    PARAM_RUN_ID,
    PARAM_SCRATCH,
    AnsweringLaunch,
    BeginStatus,
    DeclineReason,
    PassageRef,
    QuestionRecord,
    Store,
)

#: The directory under the supervisor directory holding every scratch directory,
#: beside ``launch-logs/``.
ANSWERING_DIRNAME: Final = "answering"


class LaunchStatus(StrEnum):
    """What a launch attempt did to its question."""

    #: The process started; the record is ``answering``.
    STARTED = "started"
    #: The question was declined (sources, scratch directory or spawn failed).
    DECLINED = "declined"
    #: Nothing was written: the PM answered, or the record settled, first.
    SKIPPED = "skipped"
    #: The tick budget refused a call; the question stays ``pending``.
    STOPPED = "stopped"


@dataclass(frozen=True)
class LaunchContext:
    """What launching needs besides the question."""

    store: Store
    project_id: str
    settings: AnswererSettings
    supervisor_dir: Path
    popen: PopenFactory
    tracker: LaunchTracker
    now: Callable[[], datetime]
    cf_run: CfRun
    call_timeout_seconds: float


@dataclass(frozen=True)
class Prepared:
    """A launch that is ready to journal: the entry's content and the command."""

    launch: AnsweringLaunch
    argv: tuple[str, ...]
    scratch: Path


def passage_refs(passages: PassageSet) -> tuple[PassageRef, ...]:
    """Where each passage came from, without its text (D11).

    A PM passage has no path: its record id stands for both its source and its
    question.

    Raises:
        ValueError: A passage has neither a path nor a question record.
    """
    refs: list[PassageRef] = []
    for passage in passages.passages:
        source = passage.source or passage.question_id
        if source is None:
            raise ValueError(f"passage {passage.id} has no source")
        refs.append(PassageRef(passage.id, source, passage.question_id, passage.date))
    return tuple(refs)


def prepare_launch(
    context: LaunchContext, record: QuestionRecord, budget: TickBudget
) -> Prepared | LaunchStatus:
    """Assemble the sources, make the scratch directory and build the command.

    Returns:
        ``Prepared``, or the status to report: ``STOPPED`` when the budget refused
        a call, ``DECLINED`` when the question was declined here.

    Raises:
        ValueError: A programming error: the question has no text, its node has no
            Context Forge project, or the scratch inputs are misused.
    """
    if record.question is None:
        raise ValueError(f"question {record.id} has no text to answer")
    node = context.store.get_node(record.node_id)
    if node is None or node.cf.project is None:
        raise ValueError(f"question {record.id} has no Context Forge project")
    snapshot = context.store.latest_cf_snapshots(context.project_id, node.cf.project)[1]
    sources = assemble_sources(
        context.store,
        context.project_id,
        record,
        snapshot,
        node.cf.project,
        context.settings,
        budget,
        context.cf_run,
        context.call_timeout_seconds,
    )
    if sources is None:
        return LaunchStatus.STOPPED
    if isinstance(sources, SourcesProblem):
        return _decline(context, record, sources_reason(sources), sources.detail)
    run_id = mint_run_id(context.now())
    scratch = context.supervisor_dir / ANSWERING_DIRNAME / run_id
    question = QuestionInput(slice_label(node), record.question)
    problem = _prepare_scratch(
        scratch, question, render_passages(sources), context.settings.max_cost_usd
    )
    if problem is not None:
        return _decline(context, record, DeclineReason.ANSWERING_LAUNCH_FAILED, problem)
    params = {
        ANSWER_MODEL_PARAM: context.settings.answer_model,
        CHECK_MODEL_PARAM: context.settings.check_model,
    }
    pipeline = str(answering_pipeline_path())
    argv = build_argv(pipeline, run_id, params)
    launch = AnsweringLaunch(
        node_id=record.node_id,
        run_id=run_id,
        parameters={
            PARAM_PIPELINE: pipeline,
            PARAM_PARAMS: params,
            PARAM_RUN_ID: run_id,
            PARAM_SCRATCH: str(scratch),
        },
        source_commit=sources.source_commit,
        passages=passage_refs(sources),
        dropped_pm_answers=sources.dropped_pm_answers,
    )
    return Prepared(launch, tuple(argv), scratch)


def _prepare_scratch(
    scratch: Path, question: QuestionInput, passages: str, max_cost_usd: float
) -> str | None:
    """Make and fill the scratch directory; the error text if the disk refused."""
    try:
        scratch.parent.mkdir(parents=True, exist_ok=True)
        # Exclusive: a directory is never reused, even on a run id collision.
        scratch.mkdir()
        prepare_scratch(scratch, question, passages, max_cost_usd)
    except OSError as error:
        # An expected external failure (permissions, a full disk): an answer for
        # the caller to record as a decline, not a bug. ``prepare_scratch``'s
        # ``ValueError`` is misuse and is not caught.
        return f"{type(error).__name__}: {error}"
    return None


def _decline(
    context: LaunchContext, record: QuestionRecord, reason: DeclineReason, detail: str
) -> LaunchStatus:
    context.store.decline_question(
        record.id, reason=reason, detail=cut_to_bound(detail)
    )
    return LaunchStatus.DECLINED


def launch_answering(
    context: LaunchContext, record: QuestionRecord, budget: TickBudget
) -> LaunchStatus:
    """Start the answering run of one ``pending`` question, if it can start."""
    prepared = prepare_launch(context, record, budget)
    if isinstance(prepared, LaunchStatus):
        return prepared
    begun = context.store.begin_answering(record.id, prepared.launch)
    if begun.status is not BeginStatus.BEGUN or begun.entry is None:
        return LaunchStatus.SKIPPED
    entry = begun.entry
    child = spawn(
        list(prepared.argv),
        str(prepared.scratch),
        log_paths(context.supervisor_dir, entry.id),
        context.popen,
    )
    if isinstance(child, LaunchError):
        failed = LaunchFailed(LaunchFailure.SPAWN_ERROR, None, child.detail)
        finish_answering(context.store, entry, failed, context.settings)
        return LaunchStatus.DECLINED
    context.tracker.track(entry.id, child)
    return LaunchStatus.STARTED
