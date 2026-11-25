"""The message operations stay inside the MCP call deadline (slice 240, Timeouts).

Each operation's worst case is its ``cf`` lookup at its timeout (the one ``cf get`` of
the caller's directory, 261 D10) plus its store waits at theirs. The lookup counts are
checked against what the stub ``cf`` actually saw, so a lookup added to an operation
without raising its constant fails here. Slice 262 adds the after-step term: every
operation (``inbox`` included) is followed by the after-step, whose worst case is
``AFTER_STEP_BOUND_SECONDS``. The operations that are not message operations have
their worst cases in ``OTHER_START_WORST_CASE_SECONDS`` (261 D10, D11): ``rm``
makes at most one gather, ``add`` at most one ``cf`` call and one ``git`` call, and
``status`` and ``list`` make one ``cf get`` per distinct run directory, bounded by time
and not by count (the listing, the shared gather time, and one call that starts just
before it ends). ``MCP_CALL_DEADLINE_SECONDS`` is still their cap (242 D6).
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

from amoeba.operations.deps import RUN_POLL_TIMEOUT_SECONDS, Deps
from amoeba.operations.here import ORIGIN_READ_TIMEOUT_SECONDS
from amoeba.operations.names import OperationName
from amoeba.operations.run_gather import RUNS_GATHER_SECONDS
from amoeba.operations.wake import WAKE_BOUND_SECONDS
from amoeba.store.store import BUSY_TIMEOUT_SECONDS, Store
from amoeba.store.vocabulary import Door
from amoeba.upstream.context_forge.project_of import CF_GET_TIMEOUT_SECONDS
from amoeba.wire.times import MCP_CALL_DEADLINE_SECONDS
from amoeba.wiring_gather import place_served
from amoeba.wiring_messages import (
    MESSAGE_LOOKUPS,
    MESSAGE_STORE_WAITS,
    MessageOperation,
    worst_case_seconds,
)
from amoeba.wiring_steps import AFTER_STEP_BOUND_SECONDS

#: The worst case of each start operation that is not a message operation, from the
#: constants that bound its client part, plus the start trigger (see the docstring).
_RUNS_VIEW_SECONDS = (
    CF_GET_TIMEOUT_SECONDS  # the caller's directory
    + RUN_POLL_TIMEOUT_SECONDS  # the sq listing
    + RUNS_GATHER_SECONDS  # every directory lookup shares this
    + CF_GET_TIMEOUT_SECONDS  # one lookup that starts just before it ends
)
OTHER_START_WORST_CASE_SECONDS: dict[OperationName, float] = {
    OperationName.RM: CF_GET_TIMEOUT_SECONDS + AFTER_STEP_BOUND_SECONDS,
    OperationName.ADD: (
        CF_GET_TIMEOUT_SECONDS + ORIGIN_READ_TIMEOUT_SECONDS + AFTER_STEP_BOUND_SECONDS
    ),
    OperationName.STATUS: _RUNS_VIEW_SECONDS + AFTER_STEP_BOUND_SECONDS,
    OperationName.LIST: _RUNS_VIEW_SECONDS + AFTER_STEP_BOUND_SECONDS,
}

#: Each operation run with an explicit ``member`` through its placement, which runs
#: the client part (the one ``cf`` lookup) and then the operation.
type Run = Callable[[Store, Deps], object]


def _placed(name: MessageOperation, document: dict[str, object]) -> Run:
    return lambda store, deps: place_served(
        name, store, document, DIRECTORY, Door.CLI, deps, lambda: CONFIG
    )


RUNS: dict[MessageOperation, Run] = {
    OperationName.SEND: _placed(
        OperationName.SEND,
        {
            "id": "ask",
            "to": RECIPIENT_NAME,
            "subject": "s",
            "body": "b",
            "member": SENDER_NAME,
        },
    ),
    OperationName.INBOX: _placed(OperationName.INBOX, {"member": SENDER_NAME}),
    OperationName.REPLY: _placed(
        OperationName.REPLY, {"id": "ask", "action": "accept", "member": SENDER_NAME}
    ),
    OperationName.CANCEL: _placed(
        OperationName.CANCEL, {"id": "ask", "member": SENDER_NAME}
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


def test_each_message_operation_makes_one_lookup() -> None:
    assert MESSAGE_LOOKUPS == {
        OperationName.SEND: 1,
        OperationName.INBOX: 1,
        OperationName.REPLY: 1,
        OperationName.CANCEL: 1,
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
    """The operation's worst case, plus the after-step's (which follows every message
    operation) and, for ``send``, the wake step's."""
    wake = WAKE_BOUND_SECONDS if name in WAKE_AFTER_OPERATIONS else 0.0
    return worst_case_seconds(name) + AFTER_STEP_BOUND_SECONDS + wake


def test_the_wake_bound_is_five_store_waits() -> None:
    """The legacy-move lock, the open, and the read, claim and failure transactions."""
    assert WAKE_BOUND_SECONDS == 5 * BUSY_TIMEOUT_SECONDS


def test_sends_worst_case_with_the_start_and_the_wake_is_the_design_figure() -> None:
    assert _with_start(OperationName.SEND) == (
        worst_case_seconds(OperationName.SEND)
        + AFTER_STEP_BOUND_SECONDS
        + WAKE_BOUND_SECONDS
    )
    check_below_deadline(_with_start(OperationName.SEND), MCP_CALL_DEADLINE_SECONDS)


def test_the_after_step_bound_is_one_busy_timeout_per_transaction() -> None:
    """The flag read, ``open_runs`` when a prune is due, and ``claim_work``."""
    assert AFTER_STEP_BOUND_SECONDS == 3 * BUSY_TIMEOUT_SECONDS


def test_every_message_operation_inbox_included_is_followed_by_the_after_step() -> None:
    assert set(RUNS) == {
        OperationName.SEND,
        OperationName.INBOX,
        OperationName.REPLY,
        OperationName.CANCEL,
    }
    for name in RUNS:
        extra = _with_start(name) - worst_case_seconds(name)
        wake = WAKE_BOUND_SECONDS if name in WAKE_AFTER_OPERATIONS else 0.0
        assert extra == AFTER_STEP_BOUND_SECONDS + wake


@pytest.mark.parametrize("name", RUNS, ids=lambda name: name.value)
def test_each_worst_case_with_the_start_is_below_the_mcp_call_deadline(
    name: MessageOperation,
) -> None:
    check_below_deadline(_with_start(name), MCP_CALL_DEADLINE_SECONDS)


def test_the_other_operations_with_a_worst_case_here_are_no_message_operation() -> None:
    assert not set(RUNS) & set(OTHER_START_WORST_CASE_SECONDS)


def test_the_runs_views_are_bounded_by_time_not_by_directory_count() -> None:
    """One more run directory adds no time: the gather's own limit is in the figure."""
    assert OTHER_START_WORST_CASE_SECONDS[OperationName.STATUS] == (
        CF_GET_TIMEOUT_SECONDS
        + RUN_POLL_TIMEOUT_SECONDS
        + RUNS_GATHER_SECONDS
        + CF_GET_TIMEOUT_SECONDS
        + AFTER_STEP_BOUND_SECONDS
    )
    assert (
        OTHER_START_WORST_CASE_SECONDS[OperationName.LIST]
        == OTHER_START_WORST_CASE_SECONDS[OperationName.STATUS]
    )
