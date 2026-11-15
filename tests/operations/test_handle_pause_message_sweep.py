"""``handle_pause`` sweeps messages last, beside the prune (slice 240, D6).

The question sweep's own tests are in ``test_handle_pause_sweep.py``.
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest
from store.message_support import TTL, delivery_rows, send_request

from amoeba.operations import handle_pause
from amoeba.operations.pause_models import HandlePauseOutcome
from amoeba.store.errors import StoreRowError
from amoeba.store.messages import get_message
from amoeba.store.store import Store
from amoeba.store.vocabulary import RequestState
from operations.handle_rig import PROJECT_ID, World, world
from operations.pause_support import register_member

OTHER_MEMBER = "other-member-id"
ASK = "ask"


def _overdue_request(w: World) -> None:
    """A request from the world's member that expired an hour ago."""
    register_member(w.store, OTHER_MEMBER)
    sent_at = w.deps.clock() - TTL - timedelta(hours=1)
    with w.store.write() as transaction:
        send_request(
            transaction,
            ASK,
            from_member=PROJECT_ID,
            to_member=OTHER_MEMBER,
            now=sent_at,
        )


def _state(store: Store) -> RequestState | None:
    with store.read() as transaction:
        message = get_message(transaction, ASK)
    return None if message is None else message.state


def test_an_expired_request_is_recorded_by_a_pause(tmp_path: Path) -> None:
    with world(tmp_path) as w:
        _overdue_request(w)

        result = w.handle()

        assert result.outcome is HandlePauseOutcome.RESUMED, result
        assert _state(w.store) is RequestState.EXPIRED
        with w.store.read() as transaction:
            assert [row[3] for row in delivery_rows(transaction)] == [
                "expired",
                "expired",
            ]


def test_a_failing_message_sweep_is_a_note_and_the_result_is_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    def failing(*_arguments: object) -> str | None:
        raise StoreRowError("a row the sweep could not read")

    with world(tmp_path) as w:
        _overdue_request(w)
        monkeypatch.setattr(handle_pause, "sweep_messages", failing)

        result = w.handle()

        assert result.outcome is HandlePauseOutcome.RESUMED, result
        assert result.detail is not None
        assert "message sweep: a row the sweep could not read" in result.detail
        assert "the message sweep failed after handling the pause" in caplog.text
        assert _state(w.store) is RequestState.OPEN


def test_a_busy_message_sweep_is_a_note_too(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def busy(*_arguments: object) -> str | None:
        return "message sweep did not run"

    with world(tmp_path) as w:
        monkeypatch.setattr(handle_pause, "sweep_messages", busy)

        result = w.handle()

        assert result.outcome is HandlePauseOutcome.RESUMED, result
        assert result.detail is not None
        assert "message sweep did not run" in result.detail
