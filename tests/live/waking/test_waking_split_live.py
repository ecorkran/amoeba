"""Waking with the sender and the woken member on two machines, against real ``cf``
and the real ``amoeba`` script (slice 262, D8, D10, D16, task 8.5).

The sender's checkout is on ``alpha``; the woken member's only checkout, which has the
wake command, is on ``beta``. ``alpha``'s ``send`` starts no wake and names ``beta`` in
``wake_waiting_on``; ``alpha``'s later calls start none either. ``beta``'s next call,
a plain ``amoeba list``, gets the work flag, and its after-step claims the wake and
starts it on ``beta``, where the fixture agent handles the request as on one machine.
Nothing is spent.
"""

from __future__ import annotations

from hub_fixture import SECOND

from live.waking.split import (
    SplitWaking,
    send_from_alpha,
    sender_request_states,
    wake_machines,
    wake_rows,
)
from live.waking.world import WAIT_SECONDS, fixture_agent_command, wait_until


def test_a_wake_only_beta_can_start_is_started_by_betas_next_call(
    split_waking: SplitWaking,
) -> None:
    beta, recipient = split_waking.beta, split_waking.recipient
    beta.run(recipient, "add", "--wake-command", fixture_agent_command())

    sent = send_from_alpha(split_waking, "w-1")

    assert (sent["outcome"], sent["woke"]) == ("sent", None), sent
    assert [item["machine"] for item in sent["wake_waiting_on"]] == [SECOND], sent
    # An alpha call: its after-step claims only alpha's work.
    assert sender_request_states(split_waking) == {"w-1": "open"}
    assert wake_rows(split_waking) == []

    beta.run(recipient, "list")

    assert wake_machines(split_waking) == [SECOND]
    wait_until(
        lambda: any(row.ended_at is not None for row in wake_rows(split_waking)),
        "the wake on beta to end",
        WAIT_SECONDS,
    )
    (ended,) = wake_rows(split_waking)
    assert (ended.outcome, ended.exit_code) == ("exited", 0), ended
    assert ended.log_stem is not None
    assert ended.log_stem.startswith(str(beta.client.home)), ended
    assert sender_request_states(split_waking) == {"w-1": "done"}
