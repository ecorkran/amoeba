"""Is this pause ``handle_pause``'s to answer? (slice 223, D3)

The checks run in the D3 order and the first failure is a ``Skip`` with its reason.
A Squadron or Context Forge failure is never a skip: "cannot tell" must not read as
"not mine", so it raises (exit 3) before anything is written.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from amoeba.operations.deps import Deps
from amoeba.operations.members import (
    NotAProject,
    NotInProgram,
    resolve_member,
)
from amoeba.operations.pause_models import SkipReason
from amoeba.store.models import Member, QuestionKey, QuestionRecord
from amoeba.store.questions import any_answering_run_id, get_question
from amoeba.store.store import Store
from amoeba.upstream.squadron.errors import SquadronError
from amoeba.upstream.squadron.run_file import (
    ExecutionMode,
    RunFacts,
    RunFileProblem,
    read_run_facts,
)
from amoeba.upstream.squadron.run_outcome import (
    CheckpointKind,
    PollFailure,
    RunOutcome,
    UnknownKind,
    parse_checkpoint_kind,
)


@dataclass(frozen=True)
class Skip:
    """The pause is left alone."""

    reason: SkipReason
    detail: str | None


@dataclass(frozen=True)
class Eligible:
    """A pause that is this member's to handle."""

    key: QuestionKey
    #: The question text exactly as ``sq runs wait --json`` printed it.
    question: str
    member: Member
    run_facts: RunFacts
    #: The row for this question, when an earlier call made one.
    existing: QuestionRecord | None


def check_eligibility(
    store: Store, run_id: str, directory: Path, deps: Deps
) -> Eligible | Skip:
    """Run the D3 checks for ``run_id``'s pause, from the run's ``directory``.

    Raises:
        SquadronError: ``sq`` or the run file gave no usable answer.
        ContextForgeError: ``cf`` gave no usable answer.
    """
    polled = deps.poll_run(run_id)
    if isinstance(polled, PollFailure):
        raise SquadronError(polled.reason)
    if polled.outcome is not RunOutcome.PAUSED:
        return Skip(SkipReason.NOT_PAUSED, f"the run's outcome is {polled.outcome}")
    checkpoint = polled.checkpoint
    kind = parse_checkpoint_kind(None if checkpoint is None else checkpoint.kind)
    if kind is not CheckpointKind.AGENT_QUESTION:
        return Skip(SkipReason.NOT_AGENT_QUESTION, f"checkpoint kind {_raw(kind)}")
    paused_at = checkpoint.paused_at_text if checkpoint is not None else None
    question = None if checkpoint is None else checkpoint.question
    if paused_at is None or question is None or not question.strip():
        return Skip(SkipReason.NO_QUESTION_TEXT, None)
    with store.read() as transaction:
        if any_answering_run_id(transaction, run_id):
            return Skip(SkipReason.ANSWERING_RUN, None)
    return _member_checks(
        store, QuestionKey(run_id, paused_at), question, directory, deps
    )


def _raw(kind: CheckpointKind | UnknownKind | None) -> str:
    if kind is None:
        return "not reported"
    return kind.raw if isinstance(kind, UnknownKind) else kind.value


def _member_checks(
    store: Store, key: QuestionKey, question: str, directory: Path, deps: Deps
) -> Eligible | Skip:
    resolved = resolve_member(store, directory, deps.cf_run)
    if isinstance(resolved, NotAProject):
        return Skip(SkipReason.NOT_A_PROJECT, resolved.message or None)
    if isinstance(resolved, NotInProgram):
        return Skip(SkipReason.NOT_IN_PROGRAM, f"project {resolved.cf_id}")
    # Read only after membership: a run-file problem in a non-member repo is no error.
    facts = read_run_facts(deps.squadron_runs_dir, key.run_id)
    if isinstance(facts, RunFileProblem):
        raise SquadronError(facts.reason)
    if facts.execution_mode is ExecutionMode.PROMPT_ONLY:
        return Skip(SkipReason.PROMPT_ONLY, None)
    with store.read() as transaction:
        existing = get_question(transaction, key)
    if existing is not None and existing.member_id != resolved.project_id:
        return Skip(SkipReason.OTHER_MEMBER, f"member {existing.member_id}")
    return Eligible(key, question, resolved, facts, existing)
