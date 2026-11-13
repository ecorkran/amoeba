"""The deadline invariant: ``answer`` cannot outlive the MCP call deadline
(slice 226, D12)."""

from __future__ import annotations

import pytest
from user_configs import user_config

from amoeba.config.user_config import UserConfig
from amoeba.mcp.in_process import MCP_CALL_DEADLINE_SECONDS
from amoeba.operations.resume import resume_bound_seconds
from amoeba.store.store import BUSY_TIMEOUT_SECONDS
from amoeba.wiring import (
    ANSWER_STORE_WAITS,
    DeadlineError,
    answer_bound_seconds,
    check_deadline,
)

#: ``resume_wait_seconds`` must be above zero; this is as small as a person would write.
SMALLEST_WAIT = 0.001
#: The config contract's example value.
EXAMPLE_WAIT = 60


def _with_wait(seconds: float) -> UserConfig:
    return user_config().model_copy(update={"resume_wait_seconds": seconds})


def test_the_answer_bound_is_the_resume_bound_plus_the_store_waits() -> None:
    config = _with_wait(EXAMPLE_WAIT)

    assert answer_bound_seconds(config) == (
        resume_bound_seconds(config) + ANSWER_STORE_WAITS * BUSY_TIMEOUT_SECONDS
    )


def test_a_bound_below_the_deadline_passes() -> None:
    config = _with_wait(EXAMPLE_WAIT)

    check_deadline(config, answer_bound_seconds(config) + 1)


@pytest.mark.parametrize("margin", [0, -1], ids=["equal", "above"])
def test_a_bound_at_or_above_the_deadline_names_resume_wait_seconds(
    margin: float,
) -> None:
    config = _with_wait(EXAMPLE_WAIT)

    with pytest.raises(DeadlineError, match="resume_wait_seconds"):
        check_deadline(config, answer_bound_seconds(config) + margin)


def test_the_message_names_the_largest_wait_that_would_pass() -> None:
    config = _with_wait(EXAMPLE_WAIT)
    deadline = answer_bound_seconds(config) - 10

    with pytest.raises(DeadlineError) as raised:
        check_deadline(config, deadline)

    largest = EXAMPLE_WAIT - 10
    assert f"below {largest:g}" in str(raised.value)
    check_deadline(_with_wait(largest - 1), deadline)


@pytest.mark.parametrize(
    "wait", [SMALLEST_WAIT, EXAMPLE_WAIT], ids=["smallest", "example"]
)
def test_the_real_deadline_clears_the_bound_for_ordinary_waits(wait: float) -> None:
    assert answer_bound_seconds(_with_wait(wait)) < MCP_CALL_DEADLINE_SECONDS


def test_the_real_deadline_refuses_a_wait_it_cannot_cover() -> None:
    # The config has no upper limit on ``resume_wait_seconds`` (223 validates only
    # that it is above zero), so ``check_deadline`` at start-up is the guard.
    with pytest.raises(DeadlineError, match="resume_wait_seconds"):
        check_deadline(_with_wait(MCP_CALL_DEADLINE_SECONDS), MCP_CALL_DEADLINE_SECONDS)
