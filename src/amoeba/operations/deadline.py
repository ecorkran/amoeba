"""The check that an ``answer`` fits inside the MCP call deadline (slice 226 D12,
263 D9): one rule, run against the local bound on a machine with no hub and against
the hub's resume claim time on the hub's part."""

from __future__ import annotations

from amoeba.config.user_config import UserConfig
from amoeba.operations.errors import DeadlineError


def check_within_deadline(
    config: UserConfig,
    bound_seconds: float,
    deadline_seconds: float,
    *,
    config_in: str = "",
) -> None:
    """Refuse a config whose ``answer`` could outlive the MCP call deadline.

    A call cut off after it recorded an answer and started a resume would report a
    timeout for work that happened, so the bound must be below the deadline.
    ``config_in`` says whose config it is when that is not this process's.

    Raises:
        DeadlineError: ``bound_seconds`` is not below ``deadline_seconds``; the message
            names ``resume_wait_seconds`` and the largest value allowed.
    """
    if bound_seconds < deadline_seconds:
        return
    wait = config.resume_wait_seconds
    largest = deadline_seconds - (bound_seconds - wait)
    raise DeadlineError(
        f"resume_wait_seconds is {wait:g}{config_in}, so an answer can take "
        f"{bound_seconds:g} s, which is not below the MCP call deadline of "
        f"{deadline_seconds:g} s; set resume_wait_seconds below {largest:g}"
    )
