"""``report_release``: record, correct or withdraw a member's release report
(slice 227, D2).

The member is resolved before any write transaction, so no ``cf`` call runs under a
lock. The stored-row check and the write share one ``BEGIN IMMEDIATE`` transaction.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import assert_never

from pydantic import ValidationError

from amoeba.operations.deps import Deps
from amoeba.operations.reject_codes import RejectCode
from amoeba.operations.release_member import resolve_release_member
from amoeba.operations.report_release_models import (
    ReleaseProblem,
    ReleaseReport,
    ReportMode,
    ReportOutcome,
    ReportReleaseRequest,
    ReportReleaseResult,
    malformed_problems,
)
from amoeba.store import releases
from amoeba.store.models import Release
from amoeba.store.store import Store, Transaction

__all__ = ["ReportReleaseResult", "report_release"]


class _Write(StrEnum):
    """The one store write a call makes."""

    INSERT = "insert"
    VERSION = "version"
    CORRECT = "correct"
    DELETE = "delete"
    NONE = "none"


@dataclass(frozen=True)
class _Plan:
    outcome: ReportOutcome
    write: _Write


def _plan(request: ReportReleaseRequest, stored: Release | None) -> _Plan:
    """The D2 table: what a request does given the member's stored report."""
    match request.mode:
        case ReportMode.REPORT:
            if stored is None:
                return _Plan(ReportOutcome.RECORDED, _Write.INSERT)
            if request.version is not None and request.version != stored.version:
                return _Plan(ReportOutcome.VERSIONED, _Write.VERSION)
            return _Plan(ReportOutcome.UNCHANGED, _Write.NONE)
        case ReportMode.CORRECT:
            if stored is None:
                return _Plan(ReportOutcome.REJECTED, _Write.NONE)
            return _Plan(ReportOutcome.CORRECTED, _Write.CORRECT)
        case ReportMode.WITHDRAW:
            if stored is None:
                return _Plan(ReportOutcome.REJECTED, _Write.NONE)
            return _Plan(ReportOutcome.WITHDRAWN, _Write.DELETE)
        case _:
            assert_never(request.mode)


def report_release(
    store: Store, document: object, *, directory: Path, deps: Deps
) -> ReportReleaseResult:
    """Apply ``document`` for the member whose checkout is ``directory``.

    Raises:
        ContextForgeError: ``cf`` failed while finding the member.
        StoreError: The store cannot be used.
    """
    try:
        request = ReportReleaseRequest.model_validate(document)
    except ValidationError as error:
        return _rejected(None, malformed_problems(error))
    member = resolve_release_member(store, directory, deps.cf_run)
    if isinstance(member, ReleaseProblem):
        return _rejected(None, (member,))
    now = deps.clock()
    with store.write() as transaction:
        stored = releases.release_for_commit(
            transaction, member.project_id, request.commit
        )
        plan = _plan(request, stored)
        if plan.outcome is ReportOutcome.REJECTED:
            return _rejected(member.project_id, (_not_reported(request),))
        _apply(transaction, plan.write, member.project_id, request, now=now)
        after = releases.release_for_commit(
            transaction, member.project_id, request.commit
        )
    return ReportReleaseResult(
        outcome=plan.outcome,
        member=member.project_id,
        report=None if after is None else ReleaseReport.from_release(after),
        problems=(),
    )


def _required[ValueT](value: ValueT | None, field: str) -> ValueT:
    """A field the mode rules guarantee; its absence here is a bug in ``_plan``."""
    if value is None:
        raise ValueError(f"validated request has no {field}")
    return value


def _apply(
    transaction: Transaction,
    write: _Write,
    member_id: str,
    request: ReportReleaseRequest,
    *,
    now: datetime,
) -> None:
    commit = request.commit
    match write:
        case _Write.NONE:
            return
        case _Write.DELETE:
            releases.delete_release(transaction, member_id, commit)
        case _Write.INSERT:
            releases.insert_release(
                transaction,
                member_id,
                commit,
                request.version,
                _required(request.changed, "changed"),
                _required(request.touched, "touched"),
                now,
            )
        case _Write.VERSION:
            releases.add_version(
                transaction,
                member_id,
                commit,
                _required(request.version, "version"),
                _required(request.changed, "changed"),
                _required(request.touched, "touched"),
                now,
            )
        case _Write.CORRECT:
            releases.correct_release(
                transaction,
                member_id,
                commit,
                request.version,
                _required(request.changed, "changed"),
                _required(request.touched, "touched"),
                now,
            )
        case _:
            assert_never(write)


def _not_reported(request: ReportReleaseRequest) -> ReleaseProblem:
    return ReleaseProblem(
        code=RejectCode.NOT_REPORTED,
        detail=f"this member has no report for commit {request.commit}; "
        f"nothing to {request.mode.value}",
    )


def _rejected(
    member: str | None, problems: tuple[ReleaseProblem, ...]
) -> ReportReleaseResult:
    return ReportReleaseResult(
        outcome=ReportOutcome.REJECTED, member=member, report=None, problems=problems
    )
