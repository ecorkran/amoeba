"""The ``held`` outcome's text line (slice 242, D10, 2.6)."""

from __future__ import annotations

from amoeba.cli.render.simple import render_handle_pause
from amoeba.operations.pause_models import HandlePauseOutcome, HandlePauseResult


def test_held_names_the_request_and_its_state() -> None:
    result = HandlePauseResult(
        HandlePauseOutcome.HELD, detail="accepted", request_id="guide-change"
    )

    assert render_handle_pause(result) == "held on request guide-change: accepted\n"
