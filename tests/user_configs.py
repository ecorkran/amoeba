"""One builder for ``UserConfig`` so tests state only what they care about."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from amoeba.config.user_config import NotAuthorizedItem, UserConfig
from amoeba.store.vocabulary import ConsumedMode

CONFIG_CONTRACT = Path(__file__).parents[1] / "docs" / "config-contract.md"


def example_config_text() -> str:
    """The yaml block under ``## Example`` in the config contract, not a copy."""
    example = CONFIG_CONTRACT.read_text(encoding="utf-8").split("## Example", 1)[1]
    match = re.search(r"```yaml\n(.*?)```", example, re.DOTALL)
    assert match is not None, "no yaml block under ## Example"
    return match.group(1)


def _example_number(key: str) -> int | float:
    """One numeric key of the contract's example, so its value lives only there."""
    document: dict[str, Any] = yaml.safe_load(example_config_text())
    value = document[key]
    assert isinstance(value, int | float), f"the example's {key} is not a number"
    return value


def _example_integer(key: str) -> int:
    """One integer key of the contract's example, so its value lives only there."""
    value = _example_number(key)
    assert isinstance(value, int), f"the example's {key} is not an integer"
    return value


MERGE_TO_MAIN = NotAuthorizedItem(
    key="merge_to_main",
    description="Merging a branch into the main branch.",
    screen_phrases=("merge to main", "merge into main"),
    denied_by_default=True,
)
PUSH = NotAuthorizedItem(
    key="push",
    description="Pushing commits to a remote.",
    screen_phrases=("git push",),
    denied_by_default=True,
)
DEPLOY = NotAuthorizedItem(
    key="deploy",
    description="Deploying to production.",
    screen_phrases=("deploy to prod",),
    denied_by_default=False,
)


def user_config(
    *,
    authorize_items: tuple[NotAuthorizedItem, ...] = (MERGE_TO_MAIN, PUSH, DEPLOY),
) -> UserConfig:
    return UserConfig(
        answer_model="answer-alias",
        check_model="check-alias",
        max_cost_usd=0.5,
        answer_limit=3,
        passages_max_chars=60000,
        answering_wait_seconds=600,
        resume_wait_seconds=60,
        prune_after_days=30,
        request_open_ttl_hours=_example_integer("request_open_ttl_hours"),
        max_chain_depth=_example_integer("max_chain_depth"),
        notify_poll_seconds=_example_number("notify_poll_seconds"),
        session_heartbeat_seconds=_example_number("session_heartbeat_seconds"),
        session_stale_seconds=_example_number("session_stale_seconds"),
        wake_timeout_seconds=_example_number("wake_timeout_seconds"),
        max_wakes_per_day=_example_integer("max_wakes_per_day"),
        default_rules_paths=("CLAUDE.md", "AGENTS.md"),
        default_consumed=ConsumedMode.FROM_SOURCE,
        authorize_items=authorize_items,
    )
