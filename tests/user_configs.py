"""One builder for ``UserConfig`` so tests state only what they care about."""

from __future__ import annotations

from amoeba.config.user_config import NotAuthorizedItem, UserConfig

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
        authorize_items=authorize_items,
    )
