"""What the doors get back from ``invoke``: the result type, its JSON document and
whether it was a rejection (slice 226, D4). Re-exported by ``wiring``.
"""

from __future__ import annotations

import json
from dataclasses import asdict

from pydantic import BaseModel

from amoeba.operations.answer import AnswerOutcome, AnswerResult
from amoeba.operations.changes_models import ChangesOutcome, ChangesResult
from amoeba.operations.decisions import DecisionsOutcome, DecisionsResult
from amoeba.operations.dismiss import DismissOutcome, DismissResult
from amoeba.operations.list_registry import (
    DependenciesView,
    MembersView,
    ProgramsView,
    StandingView,
)
from amoeba.operations.list_view import ListResult
from amoeba.operations.mark_read import MarkReadOutcome, MarkReadResult
from amoeba.operations.message_models import (
    CancelOutcome,
    InboxOutcome,
    ReplyOutcome,
    SendOutcome,
)
from amoeba.operations.message_results import (
    CancelResult,
    InboxResult,
    ReplyResult,
    SendResult,
)
from amoeba.operations.report_release_models import (
    ReportOutcome,
    ReportReleaseResult,
)
from amoeba.operations.retract import RetractOutcome, RetractResult
from amoeba.operations.set_up_models import SetUpOutcome, SetUpResult
from amoeba.operations.standing_models import (
    StandingOutcome,
    StandingResult,
    WithdrawOutcome,
    WithdrawResult,
)
from amoeba.operations.status import StatusOutcome, StatusResult

__all__ = ["OperationResult", "is_rejected", "result_document"]

#: What ``invoke`` returns: the in-process operations' results.
type OperationResult = (
    SetUpResult
    | ListResult
    | ProgramsView
    | MembersView
    | DependenciesView
    | StandingView
    | AnswerResult
    | StatusResult
    | DecisionsResult
    | MarkReadResult
    | DismissResult
    | RetractResult
    | ReportReleaseResult
    | ChangesResult
    | SendResult
    | InboxResult
    | ReplyResult
    | CancelResult
    | StandingResult
    | WithdrawResult
)


def result_document(result: OperationResult) -> dict[str, object]:
    """``result`` as the JSON document both doors give: enums are strings."""
    if isinstance(result, ListResult):
        return result.document()
    if isinstance(result, BaseModel):
        return result.model_dump(mode="json")
    document: dict[str, object] = json.loads(json.dumps(asdict(result)))
    return document


def is_rejected(result: OperationResult) -> bool:
    """Whether the operation refused the request (the CLI's exit 1)."""
    match result:
        case (
            SetUpResult(outcome=SetUpOutcome.REJECTED)
            | ListResult(status=StatusResult(outcome=StatusOutcome.REJECTED))
            | AnswerResult(outcome=AnswerOutcome.REJECTED)
            | StatusResult(outcome=StatusOutcome.REJECTED)
            | DecisionsResult(outcome=DecisionsOutcome.REJECTED)
            | MarkReadResult(outcome=MarkReadOutcome.REJECTED)
            | DismissResult(outcome=DismissOutcome.REJECTED)
            | RetractResult(outcome=RetractOutcome.REJECTED)
            | ReportReleaseResult(outcome=ReportOutcome.REJECTED)
            | ChangesResult(outcome=ChangesOutcome.REJECTED)
            | SendResult(outcome=SendOutcome.REJECTED)
            | InboxResult(outcome=InboxOutcome.REJECTED)
            | ReplyResult(outcome=ReplyOutcome.REJECTED)
            | CancelResult(outcome=CancelOutcome.REJECTED)
            | StandingResult(outcome=StandingOutcome.REJECTED)
            | WithdrawResult(outcome=WithdrawOutcome.REJECTED)
        ):
            return True
        case _:
            return False
