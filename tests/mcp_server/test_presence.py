"""Presence: the client name and push confirmation (slice 241, 6.3, 6.4). The member
lookup and the row the session keeps are ``test_tick``'s (slice 263).
"""

from __future__ import annotations

import logging
from pathlib import Path

import anyio
import pytest

from amoeba.mcp.presence import (
    PUSH_ANSWER_SECONDS,
    UNRECOGNIZED_CLIENT,
    PresenceState,
    client_name,
    note_event_attempted,
    note_inbox_called,
)
from mcp_server.presence_rig import (
    FakeClock,
    member_state,
)

CLIENT = "claude-code"


# --- client name (6.2) ---------------------------------------------------------


def test_a_displayable_client_name_is_kept() -> None:
    assert client_name(CLIENT) == CLIENT


@pytest.mark.parametrize("name", [None, "", "x" * 65, "bad\nname", "<script>"])
def test_any_other_name_is_the_placeholder_with_a_warning(
    name: str | None, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING):
        assert client_name(name) == UNRECOGNIZED_CLIENT

    assert [r.levelno for r in caplog.records] == [logging.WARNING]


# --- push confirmation (6.4) ---------------------------------------------------


def _state() -> tuple[PresenceState, FakeClock]:
    clock = FakeClock()

    async def build() -> PresenceState:
        return PresenceState(started_at=clock())

    return anyio.run(build), clock


def test_an_inbox_call_within_the_limit_confirms(tmp_path: Path) -> None:
    clock = FakeClock()
    state = member_state(clock, tmp_path)
    note_event_attempted(state, clock())
    clock.advance(PUSH_ANSWER_SECONDS)

    note_inbox_called(state, clock())

    # The next tick sends the yes (``test_tick``: a confirmation reaches the row).
    assert state.push_confirmed_at == clock()
    assert state.attempt_at is None


@pytest.mark.parametrize("attempted", [False, True], ids=["no-attempt", "too-late"])
def test_an_inbox_call_with_no_attempt_or_after_the_limit_does_not_confirm(
    attempted: bool,
) -> None:
    state, clock = _state()
    if attempted:
        note_event_attempted(state, clock())
        clock.advance(PUSH_ANSWER_SECONDS + 1)

    note_inbox_called(state, clock())

    assert state.push_confirmed_at is None
    assert state.attempt_at is None


def test_a_second_event_while_one_waits_does_not_reset_it() -> None:
    state, clock = _state()
    first = clock()
    note_event_attempted(state, first)
    clock.advance(PUSH_ANSWER_SECONDS - 1)

    note_event_attempted(state, clock())

    assert state.attempt_at == first


def test_an_unanswered_attempt_past_the_limit_is_replaced_by_the_next() -> None:
    state, clock = _state()
    note_event_attempted(state, clock())
    clock.advance(PUSH_ANSWER_SECONDS + 1)

    note_event_attempted(state, clock())

    assert state.attempt_at == clock()


def test_confirmation_is_sticky() -> None:
    state, clock = _state()
    note_event_attempted(state, clock())
    note_inbox_called(state, clock())
    confirmed = state.push_confirmed_at
    clock.advance(PUSH_ANSWER_SECONDS * 10)

    note_inbox_called(state, clock())

    assert confirmed is not None
    assert state.push_confirmed_at == confirmed
