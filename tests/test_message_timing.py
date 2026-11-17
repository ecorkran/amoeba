"""The message operations stay inside the MCP call deadline (slice 240, Timeouts).

Each operation's worst case is its ``cf`` lookups at their timeout plus its store waits
at theirs. The lookup counts are checked against what the stub ``cf`` actually saw, so
a lookup added to an operation without raising its constant fails here. Slice 242
adds the run-start term: ``send``, ``reply`` and ``cancel`` are followed by
``start_ended_held``, whose worst case is ``START_BOUND_SECONDS``. ``add``, ``rm``,
``status`` and ``list`` are followed by it too, but have no fixed worst case to add it
to: they make one ``cf`` lookup per member or reference in the request (``add``,
``rm``) or per run directory in the listing (``status``, ``list``), a count no constant
bounds. ``MCP_CALL_DEADLINE_SECONDS`` is their cap (242 D6).
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from cf_fixtures import OUTSIDE_ANY_PROJECT
from operations.message_support import (
    CONFIG,
    RECIPIENT_NAME,
    SENDER_NAME,
    message_cf,
    message_deps,
    open_message_store,
)
from operations.release_support import SettableClock
from operations.set_up_support import DIRECTORY, FakeCf

from amoeba.mcp.in_process import MCP_CALL_DEADLINE_SECONDS
from amoeba.operations.cancel import cancel
from amoeba.operations.deps import Deps
from amoeba.operations.inbox import inbox
from amoeba.operations.names import OperationName
from amoeba.operations.reply import reply
from amoeba.operations.request_release import MAX_STARTS_PER_CALL, START_BOUND_SECONDS
from amoeba.operations.send import send
from amoeba.operations.wake import WAKE_BOUND_SECONDS
from amoeba.store.store import BUSY_TIMEOUT_SECONDS, Store
from amoeba.upstream.context_forge.project_of import CF_GET_TIMEOUT_SECONDS
from amoeba.wiring_messages import (
    MESSAGE_LOOKUPS,
    MESSAGE_STORE_WAITS,
    MessageOperation,
    worst_case_seconds,
)
from amoeba.wiring_release import START_AFTER_OPERATIONS

#: The start operations whose worst case scales with their input, so no fixed bound
#: exists to check against the deadline (see the module docstring).
UNBOUNDED_START_OPERATIONS = frozenset(
    {OperationName.ADD, OperationName.RM, OperationName.STATUS, OperationName.LIST}
)

#: Each operation run with an explicit ``member``, so every lookup it can make happens.
type Run = Callable[[Store, Deps], object]
RUNS: dict[MessageOperation, Run] = {
    OperationName.SEND: lambda store, deps: send(
        store,
        CONFIG,
        {
            "id": "ask",
            "to": RECIPIENT_NAME,
            "subject": "s",
            "body": "b",
            "member": SENDER_NAME,
        },
        directory=DIRECTORY,
        deps=deps,
    ),
    OperationName.INBOX: lambda store, deps: inbox(
        store, {"member": SENDER_NAME}, directory=DIRECTORY, deps=deps
    ),
    OperationName.REPLY: lambda store, deps: reply(
        store,
        CONFIG,
        {"id": "ask", "action": "accept", "member": SENDER_NAME},
        directory=DIRECTORY,
        deps=deps,
    ),
    OperationName.CANCEL: lambda store, deps: cancel(
        store,
        CONFIG,
        {"id": "ask", "member": SENDER_NAME},
        directory=DIRECTORY,
        deps=deps,
    ),
}


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    yield from open_message_store(tmp_path)


def check_below_deadline(bound_seconds: float, deadline_seconds: float) -> None:
    """The check: a bound must be strictly below the deadline, or a call cut off after
    it wrote would report a timeout for work that happened."""
    assert bound_seconds < deadline_seconds, (
        f"a bound of {bound_seconds:g} s reaches the {deadline_seconds:g} s deadline"
    )


@pytest.mark.parametrize("name", RUNS, ids=lambda name: name.value)
def test_an_operation_makes_no_more_cf_lookups_than_its_constant(
    name: MessageOperation, store: Store, tmp_path: Path
) -> None:
    cf: FakeCf = message_cf(OUTSIDE_ANY_PROJECT)
    deps = message_deps(tmp_path, SettableClock(), cf)

    RUNS[name](store, deps)

    assert len(cf.calls) == MESSAGE_LOOKUPS[name]


def test_send_makes_three_lookups_and_the_others_two() -> None:
    assert MESSAGE_LOOKUPS == {
        OperationName.SEND: 3,
        OperationName.INBOX: 2,
        OperationName.REPLY: 2,
        OperationName.CANCEL: 2,
    }
    assert MESSAGE_STORE_WAITS == 3


@pytest.mark.parametrize("name", RUNS, ids=lambda name: name.value)
def test_each_worst_case_is_its_lookups_plus_its_store_waits(
    name: MessageOperation,
) -> None:
    assert worst_case_seconds(name) == (
        MESSAGE_LOOKUPS[name] * CF_GET_TIMEOUT_SECONDS
        + MESSAGE_STORE_WAITS * BUSY_TIMEOUT_SECONDS
    )


@pytest.mark.parametrize("name", RUNS, ids=lambda name: name.value)
def test_each_worst_case_is_below_the_mcp_call_deadline(
    name: MessageOperation,
) -> None:
    check_below_deadline(worst_case_seconds(name), MCP_CALL_DEADLINE_SECONDS)


def test_a_bound_that_reaches_the_deadline_fails_the_check() -> None:
    with pytest.raises(AssertionError, match="reaches"):
        check_below_deadline(MCP_CALL_DEADLINE_SECONDS, MCP_CALL_DEADLINE_SECONDS)
    with pytest.raises(AssertionError, match="reaches"):
        check_below_deadline(MCP_CALL_DEADLINE_SECONDS + 1, MCP_CALL_DEADLINE_SECONDS)


#: The operations followed by the wake step (slice 244, D11): only ``send``.
WAKE_AFTER_OPERATIONS = frozenset({OperationName.SEND})


def _with_start(name: MessageOperation) -> float:
    """The operation's worst case, plus the start trigger's and, for ``send``, the
    wake step's when they run after it."""
    start = START_BOUND_SECONDS if name in START_AFTER_OPERATIONS else 0.0
    wake = WAKE_BOUND_SECONDS if name in WAKE_AFTER_OPERATIONS else 0.0
    return worst_case_seconds(name) + start + wake


def test_the_wake_bound_is_five_store_waits() -> None:
    """The legacy-move lock, the open, and the read, claim and failure transactions."""
    assert WAKE_BOUND_SECONDS == 5 * BUSY_TIMEOUT_SECONDS


def test_sends_worst_case_with_the_start_and_the_wake_is_the_design_figure() -> None:
    assert _with_start(OperationName.SEND) == (
        worst_case_seconds(OperationName.SEND)
        + START_BOUND_SECONDS
        + WAKE_BOUND_SECONDS
    )
    check_below_deadline(_with_start(OperationName.SEND), MCP_CALL_DEADLINE_SECONDS)


def test_the_start_bound_is_one_read_and_one_write_per_start() -> None:
    assert START_BOUND_SECONDS == BUSY_TIMEOUT_SECONDS * (1 + MAX_STARTS_PER_CALL)


def test_send_reply_and_cancel_are_followed_by_the_start_and_inbox_is_not() -> None:
    message_operations = set(RUNS)
    assert message_operations & START_AFTER_OPERATIONS == {
        OperationName.SEND,
        OperationName.REPLY,
        OperationName.CANCEL,
    }


@pytest.mark.parametrize("name", RUNS, ids=lambda name: name.value)
def test_each_worst_case_with_the_start_is_below_the_mcp_call_deadline(
    name: MessageOperation,
) -> None:
    check_below_deadline(_with_start(name), MCP_CALL_DEADLINE_SECONDS)


def test_every_start_operation_is_either_bounded_here_or_named_unbounded() -> None:
    bounded = START_AFTER_OPERATIONS & set(RUNS)

    assert bounded | UNBOUNDED_START_OPERATIONS == START_AFTER_OPERATIONS
    assert not bounded & UNBOUNDED_START_OPERATIONS
