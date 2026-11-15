"""The text of ``send``, ``inbox``, ``reply`` and ``cancel`` results (slice 240)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from amoeba.cli.render.messages import (
    render_cancel,
    render_inbox,
    render_reply,
    render_send,
)
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
from amoeba.operations.quoted_data import QUOTED_DATA_NOTICE
from amoeba.operations.reject_codes import RejectCode

NOW = datetime(2026, 11, 14, 12, 0, tzinfo=UTC)


def test_a_rejection_prints_its_code_and_each_problem() -> None:
    result = SendResult.rejected(RejectCode.ID_REUSED, ("first", "second"))

    assert render_send(result, now=NOW) == (
        "rejected: id_reused: first\nrejected: id_reused: second\n"
    )


def test_a_rejected_result_without_a_code_is_a_bug_not_an_empty_code() -> None:
    with pytest.raises(ValueError, match="rejection code"):
        render_send(
            SendResult(
                outcome=SendOutcome.REJECTED,
                notice=QUOTED_DATA_NOTICE,
                rejection=None,
                request=None,
                problems=("p",),
            ),
            now=NOW,
        )
    with pytest.raises(ValueError, match="rejection code"):
        render_reply(
            ReplyResult(
                outcome=ReplyOutcome.REJECTED,
                notice=QUOTED_DATA_NOTICE,
                rejection=None,
                request=None,
                problems=("p",),
            ),
            now=NOW,
        )
    with pytest.raises(ValueError, match="rejection code"):
        render_cancel(
            CancelResult(
                outcome=CancelOutcome.REJECTED,
                notice=QUOTED_DATA_NOTICE,
                rejection=None,
                request=None,
                problems=("p",),
            ),
            now=NOW,
        )
    with pytest.raises(ValueError, match="rejection code"):
        render_inbox(
            InboxResult(
                outcome=InboxOutcome.REJECTED,
                notice=QUOTED_DATA_NOTICE,
                rejection=None,
                member=None,
                since=None,
                as_of_seq=None,
                requests=(),
                deliveries=(),
                problems=("p",),
            ),
            now=NOW,
        )
