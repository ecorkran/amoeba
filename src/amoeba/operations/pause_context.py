"""What an answering run is told about one pause (slice 223, D5).

``resolve_slice`` turns the run's ``slice`` parameter into the slice the passages are
about; the reads that follow it are in this module too. Every failure is a
``SourcesProblem`` value (the caller maps it to a decline), never a guess: a broken
slice parameter shows as a waiting question, not as a wrong slice.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final

from amoeba.answering.launch import passage_refs
from amoeba.answering.passages import (
    PassageSet,
    PmAnswer,
    SourcesProblem,
    SourcesProblemKind,
    assemble,
    render_passages,
    unreadable,
)
from amoeba.answering.settings import AnswererSettings
from amoeba.answering.source_reads import (
    CommittedSources,
    SliceRef,
    read_committed_sources,
)
from amoeba.answering.values import PassageRef
from amoeba.operations.program_sources import (
    AskerReads,
    ProgramRead,
    read_program_sources,
    without_path,
)
from amoeba.store.answers import pm_precedent
from amoeba.store.models import Member, PmPrecedent, Program
from amoeba.store.programs import get_program, members_of
from amoeba.store.store import Store
from amoeba.upstream.context_forge.cli_call import CfRun
from amoeba.upstream.context_forge.plan import (
    CFErrorDocument,
    CFInitiative,
    CFSliceList,
)
from amoeba.upstream.context_forge.plan_read import (
    read_initiatives,
    read_slice_list,
)
from amoeba.upstream.context_forge.target_read import ReadFailure, read_target
from amoeba.upstream.squadron.launch import TARGET_PARAM_KEY
from amoeba.upstream.squadron.run_file import RunFacts

#: The label of a question about a run with no ``slice`` parameter (D5). The library
#: takes the label as an argument and does not know this word.
NO_SLICE_LABEL: Final = "none"

#: One ``cf`` or ``git`` read of local files; a call that takes this long is stuck.
READ_TIMEOUT_SECONDS: Final = 30.0


@dataclass(frozen=True)
class SliceContext:
    """The slice a question is about: its label and, when there is one, where CF
    plans it. ``ref`` is ``None`` only for a run with no slice."""

    label: str
    ref: SliceRef | None


def resolve_slice(
    checkout: Path,
    cf_project_id: str,
    params: dict[str, str],
    run: CfRun,
) -> SliceContext | SourcesProblem:
    """The slice named by the run's ``slice`` parameter.

    Absent parameter: the no-slice context. A value that is not an integer, or an
    index in no initiative plan, is ``sources_missing``. A failing ``cf`` call is
    ``sources_unreadable`` with the head of its output.
    """
    raw = params.get(TARGET_PARAM_KEY)
    if raw is None:
        return SliceContext(NO_SLICE_LABEL, None)
    try:
        slice_index = int(raw)
    except ValueError:
        # Expected: the run's parameter is not a slice index; reported as missing.
        return SourcesProblem(
            SourcesProblemKind.MISSING,
            f"run parameter {TARGET_PARAM_KEY!r} is {raw!r}, not a slice index",
        )
    initiatives = read_initiatives(checkout, cf_project_id, run, READ_TIMEOUT_SECONDS)
    if isinstance(initiatives, ReadFailure):
        return unreadable(initiatives.detail)
    return _find_in_plans(
        checkout, cf_project_id, slice_index, _candidates(initiatives, slice_index), run
    )


def _candidates(
    initiatives: list[CFInitiative], slice_index: int
) -> list[CFInitiative]:
    """Initiatives that can hold the slice: index no higher than it, highest first."""
    eligible = [item for item in initiatives if item.index <= slice_index]
    return sorted(eligible, key=lambda item: item.index, reverse=True)


def _find_in_plans(
    checkout: Path,
    cf_project_id: str,
    slice_index: int,
    candidates: list[CFInitiative],
    run: CfRun,
) -> SliceContext | SourcesProblem:
    for initiative in candidates:
        plan = read_slice_list(
            checkout, cf_project_id, initiative.index, run, READ_TIMEOUT_SECONDS
        )
        if isinstance(plan, ReadFailure):
            return unreadable(plan.detail)
        if isinstance(plan, CFErrorDocument):
            continue  # this initiative has no slice plan
        found = _entry_named(plan, slice_index)
        if found is not None:
            return SliceContext(
                f"{slice_index} {found}", SliceRef(slice_index, initiative.index)
            )
    return SourcesProblem(
        SourcesProblemKind.MISSING, f"slice {slice_index} is in no initiative's plan"
    )


def _entry_named(plan: CFSliceList, slice_index: int) -> str | None:
    for entry in plan.entries:
        if entry.index == slice_index:
            return entry.name
    return None


@dataclass(frozen=True)
class PauseContext:
    """Everything the answering run is given for one pause."""

    slice_label: str
    #: The commit the committed passages were read at.
    source_commit: str
    passages: PassageSet
    #: The rendered ``passages.md``.
    passages_markdown: str
    #: Where each passage came from, for the store (never the text).
    refs: tuple[PassageRef, ...]


@dataclass(frozen=True)
class _StoredFacts:
    """What gather reads from the store, before any subprocess runs."""

    program: Program
    members: tuple[Member, ...]
    precedent: tuple[PmPrecedent, ...]


def gather(
    store: Store,
    checkout: Path,
    member: Member,
    run_facts: RunFacts,
    settings: AnswererSettings,
    run: CfRun,
) -> PauseContext | SourcesProblem:
    """The context for a question asked by ``member`` in ``checkout``.

    Reads the store once up front, then resolves the slice, reads rules and plan at
    the checkout's target, the program passages and the PM precedent, and assembles.
    The first failing step's problem is returned and nothing partial. The caller maps
    a problem to its decline reason with ``sources_reason``.
    """
    stored = _read_store(store, member)
    slice_context = resolve_slice(checkout, member.project_id, run_facts.params, run)
    if isinstance(slice_context, SourcesProblem):
        return slice_context
    committed = _read_committed(checkout, member, slice_context, settings, run)
    if not isinstance(committed, CommittedSources):
        return committed
    return _assemble(stored, member, checkout, slice_context, committed, settings, run)


def _read_store(store: Store, member: Member) -> _StoredFacts:
    with store.read() as transaction:
        program = get_program(transaction, member.program_id)
        if program is None:
            raise ValueError(f"member {member.project_id} has no program record")
        return _StoredFacts(
            program=program,
            members=members_of(transaction, member.program_id),
            precedent=pm_precedent(transaction, member.project_id),
        )


def _read_committed(
    checkout: Path,
    member: Member,
    slice_context: SliceContext,
    settings: AnswererSettings,
    run: CfRun,
) -> CommittedSources | SourcesProblem:
    target = read_target(checkout, member.project_id, run, READ_TIMEOUT_SECONDS)
    if isinstance(target, ReadFailure):
        return unreadable(target.detail)
    return read_committed_sources(
        checkout,
        target,
        slice_context.ref,
        settings.rules,
        settings.passages_max_chars,
        run,
        READ_TIMEOUT_SECONDS,
    )


def _assemble(  # noqa: PLR0913 - the pieces gather has already read
    stored: _StoredFacts,
    member: Member,
    checkout: Path,
    slice_context: SliceContext,
    committed: CommittedSources,
    settings: AnswererSettings,
    run: CfRun,
) -> PauseContext | SourcesProblem:
    program_sources = read_program_sources(
        stored.program,
        stored.members,
        ProgramRead(
            asker=member,
            asker_reads=AskerReads(checkout, committed.commit, committed.files),
            max_chars=settings.passages_max_chars - committed.chars,
            run=run,
            timeout_seconds=READ_TIMEOUT_SECONDS,
        ),
    )
    if isinstance(program_sources, SourcesProblem):
        return program_sources
    files = committed.files
    if program_sources.concept is not None and program_sources.concept.member == (
        member.project_id
    ):
        # The asker holds the concept: it is kept once, as the concept passage.
        files = without_path(files, program_sources.concept.path)
    passages = assemble(
        files,
        [_pm_answer(item) for item in stored.precedent],
        program_sources=program_sources,
        max_chars=settings.passages_max_chars,
        source_commit=committed.commit,
    )
    if isinstance(passages, SourcesProblem):
        return passages
    return PauseContext(
        slice_label=slice_context.label,
        source_commit=committed.commit,
        passages=passages,
        passages_markdown=render_passages(passages),
        refs=passage_refs(passages),
    )


def _pm_answer(item: PmPrecedent) -> PmAnswer:
    """A precedent as a passage input; its record id is the question key."""
    return PmAnswer(
        record_id=f"{item.key.run_id}@{item.key.paused_at}",
        question=item.question,
        answer=item.answer,
        date=item.recorded_at,
        slice_label=item.slice_label,
    )
