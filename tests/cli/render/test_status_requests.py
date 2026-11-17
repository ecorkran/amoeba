"""Requests and rejected calls in the text of ``list`` and ``status`` (slice 240,
D11, D12)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from amoeba.cli.render.messages import REJECTED_CALLS_SHOWN
from amoeba.cli.render.text import COLUMNS
from amoeba.cli.render.waiting import NOTHING_NEEDS_YOU, render_waiting
from amoeba.operations.decisions_models import MemberName
from amoeba.operations.message_results import RequestDirection
from amoeba.operations.quoted_data import QUOTED_DATA_NOTICE
from amoeba.operations.status_models import (
    ClosedNowEntry,
    MemberStatus,
    ProgramStatus,
    RejectedCall,
    RequestEntry,
    StatusOutcome,
    StatusResult,
)
from amoeba.store.vocabulary import ClosedReason, RequestState

NOW = datetime(2026, 11, 14, 12, 0, tzinfo=UTC)
MEMBER = MemberName(id="id-core", name="core")


def _request(request_id: str = "ask", **fields: object) -> RequestEntry:
    values: dict[str, object] = {
        "id": request_id,
        "direction": RequestDirection.SENT,
        "other_member": "id-lint",
        "other_name": "lint",
        "subject": "Please add the flag",
        "state": RequestState.OPEN,
        "created_at": NOW - timedelta(hours=3, minutes=5),
        "state_changed_at": NOW - timedelta(hours=3, minutes=5),
        "parent_id": None,
        "child_ids": (),
    }
    return RequestEntry.model_validate({**values, **fields})


def _rejected(number: int = 0) -> RejectedCall:
    return RejectedCall(
        operation="send",
        code="unknown_recipient",
        to_ref=f"nobody-{number}",
        message_id=f"id-{number}",
        parent_id=None,
        detail=f"no such member {number}",
        created_at=NOW - timedelta(minutes=number),
    )


def _text(
    *,
    requests: tuple[RequestEntry, ...] = (),
    rejected: tuple[RejectedCall, ...] = (),
    **fields: object,
) -> str:
    member = MemberStatus(
        member=MEMBER,
        runs=(),
        waiting_on_pm=(),
        requests=requests,
        rejected_calls=rejected,
    )
    values: dict[str, object] = {
        "outcome": StatusOutcome.LISTED,
        "programs": (ProgramStatus(program="trading", members=(member,)),),
        "notice": QUOTED_DATA_NOTICE if requests or rejected else None,
    }
    result = StatusResult.model_validate({**values, **fields})
    return render_waiting(result, now=NOW)


def _headings(text: str) -> list[str]:
    return [line for line in text.splitlines() if line and not line.startswith(" ")]


def test_neither_section_appears_without_requests_or_rejected_calls() -> None:
    assert _text() == NOTHING_NEEDS_YOU + "\n"


def test_a_request_shows_age_state_direction_and_subject_below_the_notice() -> None:
    text = _text(requests=(_request(),))

    assert text == (
        f"{QUOTED_DATA_NOTICE}\n\n"
        f"{NOTHING_NEEDS_YOU}\n\n"
        "Requests\n"
        "  core\n"
        "    ask · to lint · open · 3h 5m\n"
        "      subject: Please add the flag\n"
    )


def test_requests_do_not_change_nothing_needs_you() -> None:
    text = _text(requests=(_request(),), rejected=(_rejected(),))

    assert text.startswith(f"{QUOTED_DATA_NOTICE}\n\n{NOTHING_NEEDS_YOU}\n")


def test_a_received_request_says_from_and_an_expired_one_says_expired() -> None:
    text = _text(
        requests=(
            _request(direction=RequestDirection.RECEIVED, state=RequestState.EXPIRED),
        )
    )

    assert "ask · from lint · expired · 3h 5m" in text


def test_a_member_cf_no_longer_lists_is_named_by_its_id() -> None:
    text = _text(requests=(_request(other_name=None),))

    assert "to id-lint (not in Context Forge)" in text


def test_a_request_with_live_children_says_what_it_is_waiting_on() -> None:
    text = _text(requests=(_request(child_ids=("child-1", "child-2")),))

    assert "      waiting on child-1, child-2\n" in text


def test_a_request_with_no_children_does_not_say_waiting() -> None:
    assert "waiting on" not in _text(requests=(_request(),))


def test_rejected_calls_show_the_code_and_detail() -> None:
    text = _text(rejected=(_rejected(),))

    assert text == (
        f"{QUOTED_DATA_NOTICE}\n\n"
        f"{NOTHING_NEEDS_YOU}\n\n"
        "Rejected calls\n"
        "  core\n"
        "    2026-11-14 12:00 · send · unknown_recipient\n"
        "      detail: no such member 0\n"
    )


def test_only_the_newest_five_rejected_calls_show_with_a_count_of_the_rest() -> None:
    calls = tuple(_rejected(number) for number in range(REJECTED_CALLS_SHOWN + 2))

    text = _text(rejected=calls)

    assert text.count("unknown_recipient") == REJECTED_CALLS_SHOWN
    assert "no such member 4" in text
    assert "no such member 5" not in text
    assert "    and 2 more (see -j)\n" in text


def test_exactly_five_rejected_calls_have_no_more_line() -> None:
    calls = tuple(_rejected(number) for number in range(REJECTED_CALLS_SHOWN))

    assert "more (see -j)" not in _text(rejected=calls)


def test_the_notice_is_once_and_first() -> None:
    text = _text(requests=(_request(),), rejected=(_rejected(),))

    assert text.count(QUOTED_DATA_NOTICE) == 1
    assert _headings(text) == [
        QUOTED_DATA_NOTICE,
        NOTHING_NEEDS_YOU,
        "Requests",
        "Rejected calls",
    ]


def test_the_message_sections_follow_what_this_call_closed() -> None:
    closed = ClosedNowEntry(
        program="trading",
        member=MEMBER,
        run_id="run-1",
        paused_at="2026-11-14T06:48:00+00:00",
        question="Which limit?",
        closed_reason=ClosedReason.RUN_MOVED_ON,
        closed_detail="completed",
    )

    headings = _headings(_text(requests=(_request(),), closed_now=(closed,)))

    assert headings.index("Closed by this check") < headings.index("Requests")


def test_long_prose_is_cut_inside_the_line_width() -> None:
    long = "x" * 300
    text = _text(
        requests=(_request(subject=long, child_ids=(long,)),),
        rejected=(
            RejectedCall(
                operation="send",
                code="malformed",
                to_ref=None,
                message_id=None,
                parent_id=None,
                detail=long,
                created_at=NOW,
            ),
        ),
    )

    assert max(len(line) for line in text.splitlines()) <= COLUMNS
    assert len(QUOTED_DATA_NOTICE) <= COLUMNS
