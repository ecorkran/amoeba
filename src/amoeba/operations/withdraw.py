"""``withdraw``: take back a standing answer (slice 230, D3, D10).

The document is validated here, so the CLI and the MCP layer pass their input through
unchanged. One write transaction withdraws by compare-and-set, so a repeat of the
same call answers ``unchanged`` for the row the first one withdrew. There is no
un-withdraw: giving the ruling again is the undo.
"""

from __future__ import annotations

from datetime import datetime
from typing import Final

from pydantic import ValidationError

from amoeba.operations.reject_codes import validation_problems
from amoeba.operations.standing_models import (
    WithdrawOutcome,
    WithdrawRejection,
    WithdrawRequest,
    WithdrawResult,
)
from amoeba.store.standing import StandingWithdrawal, withdraw_standing
from amoeba.store.store import Store

#: The store's finding to the outcome of a row that exists.
_OUTCOMES: Final = {
    StandingWithdrawal.WITHDRAWN: WithdrawOutcome.WITHDRAWN,
    StandingWithdrawal.ALREADY_WITHDRAWN: WithdrawOutcome.UNCHANGED,
}


def withdraw(store: Store, document: object, *, now: datetime) -> WithdrawResult:
    """Withdraw the standing answer ``document`` names.

    Raises:
        StoreError: The store cannot be used; nothing was written.
    """
    try:
        request = WithdrawRequest.model_validate(document)
    except ValidationError as error:
        return WithdrawResult(
            outcome=WithdrawOutcome.REJECTED,
            rejection=WithdrawRejection.MALFORMED,
            problems=validation_problems(error),
        )
    with store.write() as transaction:
        found = withdraw_standing(transaction, request.standing_id, request.reason, now)
    if found is StandingWithdrawal.NOT_FOUND:
        return WithdrawResult(
            outcome=WithdrawOutcome.REJECTED,
            rejection=WithdrawRejection.NO_SUCH_STANDING_ANSWER,
            standing_id=request.standing_id,
            problems=(f"no standing answer {request.standing_id}",),
        )
    return WithdrawResult(outcome=_OUTCOMES[found], standing_id=request.standing_id)
