"""The message operations stay inside the MCP call deadline (slice 240, Timeouts).

Each operation's worst case is its ``cf`` lookups at their timeout plus its store waits
at theirs. The lookup counts are checked against what the stub ``cf`` actually saw, so
a lookup added to an operation without raising its constant fails here. 240 starts no
runs, so there is no run-start term; slice 242 adds one to this test.
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
from amoeba.operations.send import send
from amoeba.store.store import BUSY_TIMEOUT_SECONDS, Store
from amoeba.upstream.context_forge.project_of import CF_GET_TIMEOUT_SECONDS
from amoeba.wiring_messages import (
    MESSAGE_LOOKUPS,
    MESSAGE_STORE_WAITS,
    MessageOperation,
    worst_case_seconds,
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
