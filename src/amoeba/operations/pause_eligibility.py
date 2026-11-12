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
from amoeba.operations.pause_class import (
    ObservedPause,
    PauseClass,
    classify_no_row,
    classify_run_only,
    observed_from_document,
)
from amoeba.operations.pause_models import SkipReason
from amoeba.store.models import Member, QuestionKey, QuestionRecord
from amoeba.store.questions import any_answering_run_id, get_question
from amoeba.store.store import Store
from amoeba.upstream.squadron.errors import SquadronError
from amoeba.upstream.squadron.run_file import (
    RunFacts,
    RunFileProblem,
    read_run_facts,
)
from amoeba.upstream.squadron.run_outcome import (
    CheckpointKind,
    RunOutcomeDocument,
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
    #: What the poll said about the pause, for ``classify_pause``.
    observed: ObservedPause
    run_facts: RunFacts
    #: The row for this question, when an earlier call made one.
    existing: QuestionRecord | None


def check_eligibility(
    store: Store,
    run_id: str,
    directory: Path,
    deps: Deps,
    polled: RunOutcomeDocument,
) -> Eligible | Skip:
    """Run the D3 checks for ``run_id``'s pause, from the run's ``directory``.

    ``polled`` is the poll the caller already made (``handle_pause`` polls once, for
    the close sweep and for these checks).

    Raises:
        SquadronError: The run file gave no usable answer.
        ContextForgeError: ``cf`` gave no usable answer.
    """
    observed = observed_from_document(polled)
    early = classify_run_only(observed)
    if early is not None:
        return _run_only_skip(early, polled)
    paused_at, question = observed.paused_at, observed.question
    if paused_at is None or question is None:
        raise AssertionError("classify_run_only passed a pause without its text")
    with store.read() as transaction:
        if any_answering_run_id(transaction, run_id):
            return Skip(SkipReason.ANSWERING_RUN, None)
    key = QuestionKey(run_id, paused_at)
    return _member_checks(store, key, question, observed, directory, deps)


def _run_only_skip(pause_class: PauseClass, polled: RunOutcomeDocument) -> Skip:
    """The skip for a class decided from the run alone, with its detail."""
    match pause_class:
        case PauseClass.NOT_PAUSED:
            return Skip(SkipReason.NOT_PAUSED, f"the run's outcome is {polled.outcome}")
        case PauseClass.OTHER_CHECKPOINT:
            kind = parse_checkpoint_kind(
                None if polled.checkpoint is None else polled.checkpoint.kind
            )
            return Skip(SkipReason.NOT_AGENT_QUESTION, f"checkpoint kind {_raw(kind)}")
        case PauseClass.NO_QUESTION_TEXT:
            return Skip(SkipReason.NO_QUESTION_TEXT, None)
        case _:
            raise ValueError(f"{pause_class} is not decided from the run alone")


def _checkout_of(directory: Path) -> Path:
    """The checkout holding ``directory``: its nearest ancestor with a ``.git`` entry
    (a directory, or the file a linked worktree has), else ``directory`` itself."""
    resolved = directory.resolve()
    for candidate in (resolved, *resolved.parents):
        if (candidate / ".git").exists():
            return candidate
    return resolved


def _wrong_checkout(directory: Path, started_in: Path | None) -> Skip | None:
    """A skip when the call is not from the run's checkout (228 D10).

    Checkouts are compared, not directories: a symlinked path or a subdirectory of
    the checkout passes, a different worktree (even one nested inside) does not.
    ``None`` (a run file from before ``sq`` 0.24.24) skips the check, as before.
    """
    if started_in is None or _checkout_of(directory) == _checkout_of(started_in):
        return None
    detail = f"called from {directory}; the run was started in {started_in}"
    if not started_in.exists():
        detail += (
            " (that directory no longer exists; use Squadron's own commands, such as "
            "`sq run --resume`, to continue or leave the run)"
        )
    return Skip(SkipReason.WRONG_CHECKOUT, detail)


def _raw(kind: CheckpointKind | UnknownKind | None) -> str:
    if kind is None:
        return "not reported"
    return kind.raw if isinstance(kind, UnknownKind) else kind.value


def _member_checks(
    store: Store,
    key: QuestionKey,
    question: str,
    observed: ObservedPause,
    directory: Path,
    deps: Deps,
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
    with store.read() as transaction:
        existing = get_question(transaction, key)
    if existing is None and classify_no_row(facts) is PauseClass.PROMPT_ONLY:
        return Skip(SkipReason.PROMPT_ONLY, None)
    # Whatever the row state: a dead claim or an unresumed answer is never resumed
    # from a second worktree either.
    wrong = _wrong_checkout(directory, facts.working_directory)
    if wrong is not None:
        return wrong
    if existing is not None and existing.member_id != resolved.project_id:
        return Skip(SkipReason.OTHER_MEMBER, f"member {existing.member_id}")
    return Eligible(key, question, resolved, observed, facts, existing)
