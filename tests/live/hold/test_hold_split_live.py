"""A run held on a request, with the two repos on two machines, against real ``sq`` and
models (slice 262, D10, D16, task 8.5).

The asking repo's checkout is on ``alpha`` and the repo the request goes to is on
``beta``. ``alpha`` sends the request, its run pauses, and one ``handle-pause`` there
holds the question. ``beta`` replies ``done``; ``beta``'s calls start nothing, because
the question belongs to ``alpha``. ``alpha``'s next call, a plain ``amoeba list``,
gets the work flag, and its after-step claims and starts the held question's
``handle-pause``, which answers and resumes the run as on one machine. Nothing is
retried.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from hub_fixture import FIRST

from amoeba.upstream.squadron.launch import mint_run_id
from amoeba.upstream.squadron.run_outcome import RunOutcome, RunOutcomeDocument
from live.hold.harness import (
    amoeba_document,
    handle_pause_once,
    reply_done,
    send_request,
    start_held_pause,
)
from live.hold.split import SplitHold, observe, poll_until_ended
from live.hold.test_hold_live import FAITHFUL_RESULT


def test_a_done_from_beta_is_taken_up_by_alphas_next_call_and_resumes(
    split_hold: SplitHold,
) -> None:
    hold = split_hold.hold
    stamp = datetime.now(UTC)
    run_id = mint_run_id(stamp)
    request_id = f"hold-split-{stamp:%Y%m%dT%H%M%S%f}"
    send_request(hold, request_id)
    started = start_held_pause(hold, run_id, request_id)
    assert isinstance(started.poll, RunOutcomeDocument), started.sq_output
    assert started.poll.outcome is RunOutcome.PAUSED, started.sq_output

    first = handle_pause_once(hold, run_id)

    assert (first["outcome"], first["request_id"]) == ("held", request_id), first
    held = observe(split_hold, run_id)
    assert (held.state, held.machine, held.start_count) == (
        "waiting_on_request",
        FIRST,
        0,
    ), held

    reply_done(hold, request_id, FAITHFUL_RESULT)

    # beta's calls ran their after-step, which claims only beta's work.
    replied = observe(split_hold, run_id)
    assert (replied.state, replied.start_count) == ("waiting_on_request", 0), replied

    amoeba_document(hold.asker, "list")

    taken = observe(split_hold, run_id)
    assert taken.start_count == 1, taken
    observed = poll_until_ended(split_hold, run_id)
    assert (observed.state, observed.resume_outcome) == ("answered", "resumed"), (
        observed
    )
    decisions = amoeba_document(hold.asker, "decisions")
    (record,) = [r for r in decisions["records"] if r["run_id"] == run_id]
    _assert_answered_from_the_request(dict(record), request_id)


def _assert_answered_from_the_request(record: dict[str, Any], request_id: str) -> None:
    assert record["request_id"] == request_id
    assert record["answered_by"] == "answerer"
    based_on = record["based_on"]
    sources = [passage["source"] for passage in based_on["cited"]]
    assert request_id in sources, based_on
    assert based_on["check_verdict"] == "yes", based_on
    assert record["resume"]["outcome"] == "resumed"
