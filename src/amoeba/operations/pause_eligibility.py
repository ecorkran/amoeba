"""Is this pause ``handle_pause``'s to answer? (slice 223, D3)

The checks run in the D3 order and the first failure is a ``Skip`` with its reason.
A Squadron or Context Forge failure is never a skip: "cannot tell" must not read as
"not mine", so it raises (exit 3) before anything is written.

A Context Forge project in no program is registered here with the defaults, as a bare
``amoeba add`` in its checkout would, and then handled: the hook is set once for the
whole machine, so the first pause in a repo is what makes it a member. The store reads
(the sweep of older rows, the caller, the row) are one step, ``pause_begin`` (262 D4).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path

from amoeba.operations.deps import Deps
from amoeba.operations.here import gather_caller, git_root
from amoeba.operations.here_document import HereCaller, HereNotAProject
from amoeba.operations.pause_class import (
    ObservedPause,
    PauseClass,
    classify_no_row,
    classify_run_only,
    observed_from_document,
)
from amoeba.operations.pause_models import SkipReason
from amoeba.operations.question_judge import SweepResult
from amoeba.operations.question_sweep import fate_of_poll
from amoeba.operations.set_up_models import SetUpOutcome, SetUpResult
from amoeba.operations.steps.models import PAUSE_BEGIN
from amoeba.operations.steps.models_pause import (
    FateFields,
    PauseBeginReply,
    PauseBeginRequest,
)
from amoeba.operations.store_steps import Steps
from amoeba.store.models import Member, QuestionKey, QuestionRecord
from amoeba.upstream.squadron.errors import SquadronError
from amoeba.upstream.squadron.run_file import (
    RunFacts,
    RunFileProblem,
    read_run_facts,
)
from amoeba.upstream.squadron.run_outcome import RunOutcomeDocument

logger = logging.getLogger(__name__)

#: Registers the project the call came from with ``add``'s defaults: gathers its
#: checkout, runs ``add`` with an empty document (in process or through the door) and
#: returns its result. The pause modules import neither ``add`` nor the store (D5).
type Register = Callable[[Path], SetUpResult]


@dataclass(frozen=True)
class Skip:
    """The pause is left alone."""

    reason: SkipReason
    detail: str | None
    #: What ``pause_begin`` closed on the way; empty when the call never reached it.
    swept: SweepResult = SweepResult()


@dataclass(frozen=True)
class Eligible:
    """A pause that is this member's to handle."""

    key: QuestionKey
    #: The question text exactly as ``sq runs wait --json`` printed it.
    question: str
    member: Member
    #: The Context Forge project id of the checkout the call came from: what ``cf -p``
    #: takes. The member's id is never given to ``cf`` (261 D6).
    cf_project_id: str
    #: What the poll said about the pause, for ``classify_pause``.
    observed: ObservedPause
    run_facts: RunFacts
    #: The row for this question, when an earlier call made one.
    existing: QuestionRecord | None
    #: The hub's whole answer: settings, limits, link, request, ``claim_stale``.
    begun: PauseBeginReply


def check_eligibility(  # noqa: PLR0913 - the pieces of one call
    steps: Steps,
    run_id: str,
    directory: Path,
    deps: Deps,
    polled: RunOutcomeDocument,
    register: Register,
) -> Eligible | Skip:
    """Run the D3 checks for ``run_id``'s pause, from the run's ``directory``.

    ``polled`` is the poll the caller already made (``handle_pause`` polls once, for
    the close sweep and for these checks). A pause the run alone decides
    (``classify_run_only``) makes no ``cf`` call.

    Raises:
        SquadronError: The run file gave no usable answer.
        ContextForgeError: ``cf`` gave no usable answer.
    """
    observed = observed_from_document(polled)
    request = _request_for(run_id, polled, observed)
    if classify_run_only(observed) is not None:
        return _skip_of(steps.run(PAUSE_BEGIN, request))
    here = gather_caller(directory, deps.cf_run)
    begun = steps.run(PAUSE_BEGIN, request.model_copy(update={"here": here}))
    if begun.not_in_program is not None:
        problem = _register(register, directory, begun.not_in_program)
        if problem is not None:
            return Skip(SkipReason.NOT_IN_PROGRAM, problem, begun.swept)
        begun = steps.run(PAUSE_BEGIN, request.model_copy(update={"here": here}))
        if begun.not_in_program is not None:
            detail = f"project {begun.not_in_program}; still no member after add"
            return Skip(SkipReason.NOT_IN_PROGRAM, detail, begun.swept)
    if begun.skip is not None:
        return _skip_of(begun)
    return _member_checks(begun, here, run_id, directory, deps, observed)


def _skip_of(begun: PauseBeginReply) -> Skip:
    if begun.skip is None:
        raise AssertionError("pause_begin skipped a pause without saying why")
    return Skip(begun.skip, begun.skip_detail, begun.swept)


def _register(register: Register, directory: Path, cf_id: str) -> str | None:
    """Register the project with ``add``'s defaults; the text saying why it did not
    take, or ``None`` when it did."""
    result = register(directory)
    if result.outcome is not SetUpOutcome.REJECTED:
        logger.info("registered %s", cf_id)
        return None
    problems = "; ".join(problem.detail for problem in result.problems)
    return f"project {cf_id}; registering it was rejected: {problems}"


def _request_for(
    run_id: str, polled: RunOutcomeDocument, observed: ObservedPause
) -> PauseBeginRequest:
    fate = fate_of_poll(polled)
    return PauseBeginRequest(
        run_id=run_id,
        here=None,
        outcome=str(polled.outcome),
        paused=observed.paused,
        checkpoint_kind=observed.kind,
        paused_at=observed.paused_at,
        question=observed.question,
        fate=None
        if fate is None
        else FateFields(
            reason=fate.reason,
            detail=fate.detail,
            current_paused_at=fate.current_paused_at,
        ),
    )


def _member_checks(  # noqa: PLR0913 - the pieces of one call
    begun: PauseBeginReply,
    here: HereCaller | HereNotAProject,
    run_id: str,
    directory: Path,
    deps: Deps,
    observed: ObservedPause,
) -> Eligible | Skip:
    member = begun.member
    if member is None or observed.paused_at is None or observed.question is None:
        raise AssertionError("pause_begin returned no member past its skips")
    if not isinstance(here, HereCaller):
        raise ValueError("a member's checkout has a gathered project id")
    key = QuestionKey(run_id, observed.paused_at)
    # Read only after membership: a run-file problem in a non-member repo is no error.
    facts = read_run_facts(deps.squadron_runs_dir, key.run_id)
    if isinstance(facts, RunFileProblem):
        raise SquadronError(facts.reason)
    existing = begun.row
    swept = begun.swept
    if existing is None and classify_no_row(facts) is PauseClass.PROMPT_ONLY:
        return Skip(SkipReason.PROMPT_ONLY, None, swept)
    # Whatever the row state: a dead claim or an unresumed answer is never resumed
    # from a second worktree either.
    wrong = _wrong_checkout(directory, facts.working_directory)
    if wrong is not None:
        return replace(wrong, swept=swept)
    if existing is not None and existing.member_id != member.project_id:
        return Skip(SkipReason.OTHER_MEMBER, f"member {existing.member_id}", swept)
    if begun.other_machine is not None:
        detail = f"the question is on {begun.other_machine}"
        return Skip(SkipReason.OTHER_MACHINE, detail, swept)
    return Eligible(
        key,
        observed.question,
        member,
        here.project_id,
        observed,
        facts,
        existing,
        begun,
    )


def _checkout_of(directory: Path) -> Path:
    """The checkout holding ``directory``: its nearest ancestor with a ``.git`` entry
    (a directory, or the file a linked worktree has), else ``directory`` itself."""
    return git_root(directory) or directory.resolve()


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
