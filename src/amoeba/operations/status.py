"""``status``: what is running, paused and waiting on the PM (slice 224, D2, D4, D8).

The flow: resolve the scope; read the store once; list runs once; place them; classify
the paused ones; join the waiting questions; ask ``cf`` for names once. The store is
read first, so no subprocess runs inside a store transaction. The placement,
classification and waiting-question steps are in ``status_placement``, ``status_runs``
and ``status_waiting``; the result models are in ``status_models`` and re-exported here.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    StrictStr,
    StringConstraints,
    ValidationError,
)

from amoeba.config.user_config import UserConfig
from amoeba.operations.decisions_models import MemberName
from amoeba.operations.deps import Deps
from amoeba.operations.members import (
    ContextForgeError,
    NotAProject,
    NotInProgram,
    resolve_member,
)
from amoeba.operations.reject_codes import (
    RejectCode,
    unknown_program_problem,
    validation_problems,
)
from amoeba.operations.status_models import (
    MemberStatus,
    ProgramStatus,
    StatusOutcome,
    StatusResult,
)
from amoeba.operations.status_placement import place_runs
from amoeba.operations.status_runs import MemberRun, classify_runs
from amoeba.operations.status_waiting import MemberWaiting, waiting_entries
from amoeba.store.models import Member
from amoeba.store.programs import get_program, list_programs, members_of
from amoeba.store.questions import latest_rows_by_run, open_questions
from amoeba.store.store import Store, Transaction
from amoeba.upstream.context_forge.cli_call import CfCallFailed
from amoeba.upstream.context_forge.project_of import project_of
from amoeba.upstream.squadron.errors import SquadronError
from amoeba.upstream.squadron.run_list import RunListProblem

__all__ = [
    "ScopeRejected",
    "ScopedProgram",
    "StatusOutcome",
    "StatusRequest",
    "StatusResult",
    "resolve_scope",
    "status",
]

#: A stripped, non-empty string.
_NonBlank = Annotated[StrictStr, StringConstraints(strip_whitespace=True, min_length=1)]


class StatusRequest(BaseModel):
    """What ``status`` is asked: optionally one program."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    program: _NonBlank | None = None


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
    store: Store, directory: Path, program: str | None, deps: Deps
) -> tuple[ScopedProgram, ...] | ScopeRejected:
    """The programs ``status`` covers (D2).

    ``program`` given: that program, or ``unknown_program`` listing the known ids.
    Otherwise the program of the member ``directory`` is in, or every program when it
    is in none.

    Raises:
        ContextForgeError: ``cf`` failed while resolving ``directory``. This is an
            operational error and never widens the scope.
    """
    if program is not None:
        with store.read() as transaction:
            unknown = unknown_program_problem(transaction, program)
            if unknown is not None:
                return ScopeRejected(RejectCode.UNKNOWN_PROGRAM, (unknown,))
            return (_scoped(transaction, program),)
    resolved = resolve_member(store, directory, deps.cf_run)
    with store.read() as transaction:
        if isinstance(resolved, NotAProject | NotInProgram):
            return tuple(
                _scoped(transaction, entry.program_id)
                for entry in list_programs(transaction)
            )
        return (_scoped(transaction, resolved.program_id),)


def _scoped(transaction: Transaction, program_id: str) -> ScopedProgram:
    if get_program(transaction, program_id) is None:
        raise ValueError(f"program {program_id!r} vanished while it was read")
    return ScopedProgram(program_id, members_of(transaction, program_id))


def status(
    store: Store,
    config: UserConfig,
    document: object,
    *,
    directory: Path,
    deps: Deps,
) -> StatusResult:
    """What is running, paused and waiting on the PM, per program and member.

    Raises:
        SquadronError: ``sq runs list --json`` gave no usable listing.
        ContextForgeError: ``cf`` gave no usable answer, or no name for a member.
        StoreError: The store cannot be used.
    """
    try:
        request = StatusRequest.model_validate(document)
    except ValidationError as error:
        return _rejected(RejectCode.MALFORMED, validation_problems(error))
    scope = resolve_scope(store, directory, request.program, deps)
    if isinstance(scope, ScopeRejected):
        return _rejected(scope.code, scope.problems)
    members = {m.project_id: m for entry in scope for m in entry.members}
    with store.read() as transaction:
        open_rows = open_questions(transaction, list(members))
        rows = latest_rows_by_run(transaction, list(members))
    listed = deps.list_runs()
    if isinstance(listed, RunListProblem):
        raise SquadronError(
            f"status needs `sq runs list --json` (Squadron with #303): {listed.reason}"
        )
    placement = place_runs(
        listed,
        members,
        deps.answering_dir,
        lambda found: project_of(directory=found, run=deps.cf_run),
    )
    runs = classify_runs(
        placement.placed,
        rows,
        deps.squadron_runs_dir,
        config.answering_wait_seconds,
        deps.clock(),
    )
    waiting = waiting_entries(open_rows, listed)
    names = _names(members, deps)
    return StatusResult(
        outcome=StatusOutcome.LISTED,
        programs=tuple(_program_status(entry, names, runs, waiting) for entry in scope),
        unplaced_runs=placement.unplaced,
    )


def _rejected(code: RejectCode, problems: tuple[str, ...]) -> StatusResult:
    return StatusResult(
        outcome=StatusOutcome.REJECTED, rejection=code, problems=problems
    )


def _names(members: dict[str, Member], deps: Deps) -> dict[str, str]:
    """Names of the members in scope, from one ``cf`` call (none if there are none)."""
    if not members:
        return {}
    names = deps.project_names()
    if isinstance(names, CfCallFailed):
        raise ContextForgeError(names.detail)
    missing = sorted(set(members) - set(names))
    if missing:
        raise ContextForgeError(f"Context Forge lists no project named for {missing}")
    return names


def _program_status(
    entry: ScopedProgram,
    names: dict[str, str],
    runs: list[MemberRun],
    waiting: list[MemberWaiting],
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
            )
            for member in entry.members
        ),
    )
