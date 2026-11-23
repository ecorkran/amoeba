"""``status``: what is running, paused and waiting on the PM (slice 224, D2, D4, D8).

The flow: resolve the scope; read the store once; take the runs from the ``runs``
document (the client part read ``sq``, ``cf``, the run files and the calls log, 261
D11); place them; classify the paused ones; join the waiting questions. The store is
read first, so no subprocess runs inside a store transaction, and this module runs
none. The placement, classification and waiting-question steps are in
``status_placement``, ``status_runs`` and ``status_waiting``; the result models are in
``status_models`` and re-exported here.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    ValidationError,
)

from amoeba.config.user_config import NonBlank, UserConfig
from amoeba.operations.caller import NotAProject, NotInProgram, find_caller
from amoeba.operations.decisions_models import MemberName
from amoeba.operations.deps import Deps
from amoeba.operations.here_document import HereCaller, HereNotAProject
from amoeba.operations.message_sweep import sweep_messages
from amoeba.operations.pause_class import PauseClass
from amoeba.operations.prune_models import PruneReport
from amoeba.operations.question_sweep import SweepResult
from amoeba.operations.question_sweep_scope import sweep_scope
from amoeba.operations.quoted_data import QUOTED_DATA_NOTICE
from amoeba.operations.reject_codes import (
    RejectCode,
    unknown_program_problem,
    validation_problems,
)
from amoeba.operations.runs_document import (
    RunsDocument,
    RunStanding,
    left_out_text,
    standings,
)
from amoeba.operations.status_calls import attach_last_calls
from amoeba.operations.status_closed import closed_now_entries
from amoeba.operations.status_models import (
    MemberStatus,
    ProgramStatus,
    SessionEntry,
    StatusOutcome,
    StatusResult,
    WakeStatus,
)
from amoeba.operations.status_placement import place_runs
from amoeba.operations.status_requests import MemberMessages, read_member_messages
from amoeba.operations.status_runs import (
    MemberRun,
    classify_runs,
    held_request_states,
)
from amoeba.operations.status_sessions import read_member_sessions
from amoeba.operations.status_waiting import MemberWaiting, waiting_entries
from amoeba.operations.wake_status import read_member_wakes
from amoeba.store.checkouts import checkouts_on_machine
from amoeba.store.errors import StoreRowError
from amoeba.store.machines import acting_machine_id
from amoeba.store.models import Member, QuestionRecord
from amoeba.store.programs import get_program, list_programs, members_of
from amoeba.store.questions import (
    latest_rows_by_run,
    open_questions,
    sweep_candidates,
)
from amoeba.store.store import Store, Transaction
from amoeba.upstream.squadron.errors import SquadronError

__all__ = [
    "ScopeRejected",
    "ScopedProgram",
    "StatusOutcome",
    "StatusRequest",
    "StatusResult",
    "resolve_scope",
    "status",
]


class StatusRequest(BaseModel):
    """What ``status`` is asked: optionally one program."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    program: NonBlank | None = None


@dataclass(frozen=True)
class ScopedProgram:
    """A program in scope with its members, possibly none."""

    program_id: str
    members: tuple[Member, ...]


@dataclass(frozen=True)
class ScopeRejected:
    """The scope could not be resolved from the request."""

    code: RejectCode
    problems: tuple[str, ...]


def resolve_scope(
    store: Store, here: HereCaller | HereNotAProject, program: str | None
) -> tuple[ScopedProgram, ...] | ScopeRejected:
    """The programs ``status`` covers (D2).

    ``program`` given: that program, or ``unknown_program`` listing the known ids.
    Otherwise the program of the member whose checkout is ``here``, or every program
    when it is in none.
    """
    if program is not None:
        with store.read() as transaction:
            unknown = unknown_program_problem(transaction, program)
            if unknown is not None:
                return ScopeRejected(RejectCode.UNKNOWN_PROGRAM, (unknown,))
            return (_scoped(transaction, program),)
    with store.read() as transaction:
        resolved = find_caller(transaction, acting_machine_id(transaction), here)
        if isinstance(resolved, NotAProject | NotInProgram):
            return tuple(
                _scoped(transaction, entry.program_id)
                for entry in list_programs(transaction)
            )
        return (_scoped(transaction, resolved.program_id),)


def _scoped(transaction: Transaction, program_id: str) -> ScopedProgram:
    if get_program(transaction, program_id) is None:
        raise StoreRowError(f"program {program_id!r} vanished while it was read")
    return ScopedProgram(program_id, members_of(transaction, program_id))


def status(
    store: Store,
    config: UserConfig,
    document: object,
    *,
    here: HereCaller | HereNotAProject,
    runs: RunsDocument,
    clock: Callable[[], datetime],
    local: Deps | None,
) -> StatusResult:
    """What is running, paused and waiting on the PM, per program and member.

    ``here`` is the caller's gathered project and ``runs`` the machine's gathered runs.
    ``local`` is this machine's own edges; with it the close sweep and the pruning of
    local scratch and logs run, and on the hub (``None``) they do not (261 D11): they
    read the files of the machine that ran ``sq``.

    Raises:
        SquadronError: The document says ``sq runs list --json`` gave no usable
            listing.
        StoreError: The store cannot be used.
    """
    try:
        request = StatusRequest.model_validate(document)
    except ValidationError as error:
        return _rejected(RejectCode.MALFORMED, validation_problems(error))
    scope = resolve_scope(store, here, request.program)
    if isinstance(scope, ScopeRejected):
        return _rejected(scope.code, scope.problems)
    members = {m.project_id: m for entry in scope for m in entry.members}
    # Before the reads, so an expired request shows as recorded; a busy store is a
    # problem text, never a failure (the reads apply effective_state).
    message_problem = sweep_messages(store, config, clock())
    with store.read() as transaction:
        candidates = sweep_candidates(transaction, list(members))
        rows = latest_rows_by_run(transaction, list(members))
        requests = held_request_states(transaction, rows, clock())
    if runs.listing_problem is not None:
        raise SquadronError(
            "status needs `sq runs list --json` (Squadron with #303): "
            f"{runs.listing_problem}"
        )
    # The listing is ``--all`` so the sweep can tell a finished run from an unknown
    # one; completed runs stay out of the per-member run lists, as before.
    with store.read() as transaction:
        by_checkout = _members_by_checkout(transaction, members)
    placement = place_runs(runs.open_runs, by_checkout)
    member_runs = classify_runs(
        placement.placed,
        rows,
        requests,
        config.answering_wait_seconds,
        clock(),
    )
    with_calls = attach_last_calls(member_runs, runs)
    member_runs = with_calls.runs
    names = _names(members)
    standing = standings(runs)
    swept = _sweep(store, config, candidates, standing, local, clock())
    # What is still open after the sweep. After a failed write that is everything,
    # shown as before the sweep.
    with store.read() as transaction:
        open_rows = open_questions(transaction, list(members))
    waiting = waiting_entries(open_rows, standing)
    messages = read_member_messages(store, members, clock())
    sessions = read_member_sessions(
        store, members, clock(), config.session_stale_seconds
    )
    wakes = read_member_wakes(store, members, clock(), config.max_wakes_per_day)
    program_of = {
        m.project_id: entry.program_id for entry in scope for m in entry.members
    }
    pruned = _prune(store, config, local, clock())
    return StatusResult(
        outcome=StatusOutcome.LISTED,
        notice=QUOTED_DATA_NOTICE
        if _shows_others_text(messages, member_runs, waiting)
        else None,
        programs=tuple(
            _program_status(
                entry, names, member_runs, waiting, messages, sessions, wakes
            )
            for entry in scope
        ),
        unplaced_runs=placement.unplaced,
        closed_now=closed_now_entries(swept, program_of, names),
        sweep_problem=_joined(message_problem, swept.problem),
        file_problems=_file_problems(runs, with_calls.problems, pruned.problems),
    )


def _sweep(  # noqa: PLR0913 - the pieces status already has in hand
    store: Store,
    config: UserConfig,
    candidates: Sequence[QuestionRecord],
    standing: Mapping[str, RunStanding],
    local: Deps | None,
    now: datetime,
) -> SweepResult:
    if local is None:
        return SweepResult()
    return sweep_scope(
        store, config, candidates, standing, local.squadron_runs_dir, now
    )


def _prune(
    store: Store, config: UserConfig, local: Deps | None, now: datetime
) -> PruneReport:
    if local is None:
        return PruneReport(removed=0, problems=())
    return local.prune(store, now=now, after_days=config.prune_after_days)


def _file_problems(
    runs: RunsDocument, call_problems: tuple[str, ...], prune_problems: tuple[str, ...]
) -> tuple[str, ...]:
    """The call-log and prune problems, and the sentence for a cut document."""
    cut = left_out_text(runs.left_out)
    return (*call_problems, *(() if cut is None else (cut,)), *prune_problems)


def _joined(*problems: str | None) -> str | None:
    """The sweep problems that happened, one text, or ``None`` when none did."""
    found = [problem for problem in problems if problem is not None]
    return "; ".join(found) if found else None


def _shows_others_text(
    messages: dict[str, MemberMessages],
    runs: list[MemberRun],
    waiting: list[MemberWaiting],
) -> bool:
    """Whether any entry shown came from another agent: a request, a rejected call,
    a held run, or a waiting entry whose reason is its request's (242 D9)."""
    if any(item.requests or item.rejected_calls for item in messages.values()):
        return True
    if any(item.entry.pause is PauseClass.WAITING_ON_REQUEST for item in runs):
        return True
    return any(item.entry.request_id is not None for item in waiting)


def _rejected(code: RejectCode, problems: tuple[str, ...]) -> StatusResult:
    return StatusResult(
        outcome=StatusOutcome.REJECTED, rejection=code, problems=problems
    )


def _members_by_checkout(
    transaction: Transaction, members: dict[str, Member]
) -> dict[str, Member]:
    """The members in scope by the Context Forge project id of each of their checkouts
    on this machine: a run is placed by its directory's project (261 D11)."""
    return {
        checkout.cf_project_id: members[checkout.member_id]
        for checkout in checkouts_on_machine(
            transaction, acting_machine_id(transaction)
        )
        if checkout.member_id in members
    }


def _names(members: dict[str, Member]) -> dict[str, str]:
    """The stored name of each member in scope (261 D13)."""
    return {project_id: member.name for project_id, member in members.items()}


def _program_status(
    entry: ScopedProgram,
    names: dict[str, str],
    runs: list[MemberRun],
    waiting: list[MemberWaiting],
    messages: dict[str, MemberMessages],
    sessions: dict[str, tuple[SessionEntry, ...]],
    wakes: dict[str, WakeStatus],
) -> ProgramStatus:
    return ProgramStatus(
        program=entry.program_id,
        members=tuple(
            MemberStatus(
                member=MemberName(id=member.project_id, name=names[member.project_id]),
                runs=tuple(
                    run.entry for run in runs if run.member_id == member.project_id
                ),
                waiting_on_pm=tuple(
                    item.entry
                    for item in waiting
                    if item.member_id == member.project_id
                ),
                requests=messages[member.project_id].requests,
                rejected_calls=messages[member.project_id].rejected_calls,
                sessions=sessions[member.project_id],
                wake=wakes.get(member.project_id),
            )
            for member in entry.members
        ),
    )
