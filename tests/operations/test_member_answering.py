"""``answering_for``: per-member not-authorized items and the settings they feed."""

from __future__ import annotations

import pytest
from user_configs import DEPLOY, MERGE_TO_MAIN, PUSH, user_config

from amoeba.config.user_config import ConfigError
from amoeba.operations.member_answering import answering_for
from amoeba.store.models import MemberSettings


def _member(
    project_id: str = "m",
    *,
    allow: tuple[str, ...] = (),
    deny: tuple[str, ...] = (),
    rules_paths: tuple[str, ...] = ("CLAUDE.md",),
) -> MemberSettings:
    return MemberSettings(
        project_id=project_id,
        rules_paths=rules_paths,
        authorize_allow=allow,
        authorize_deny=deny,
    )


def test_allowing_an_item_drops_it_for_that_member_only() -> None:
    config = user_config()

    permissive = answering_for(_member("a", allow=("merge_to_main",)), config)
    strict = answering_for(_member("b"), config)

    assert MERGE_TO_MAIN not in permissive.not_authorized
    assert "merge to main" not in permissive.settings.reserved_terms
    assert MERGE_TO_MAIN in strict.not_authorized
    assert "merge to main" in strict.settings.reserved_terms
    assert PUSH in permissive.not_authorized


def test_denying_a_default_allowed_item_adds_it_for_that_member_only() -> None:
    config = user_config()

    denying = answering_for(_member("a", deny=("deploy",)), config)
    other = answering_for(_member("b"), config)

    assert DEPLOY in denying.not_authorized
    assert "deploy to prod" in denying.settings.reserved_terms
    assert DEPLOY not in other.not_authorized
    assert "deploy to prod" not in other.settings.reserved_terms


def test_items_keep_config_order_and_phrases_follow_them() -> None:
    config = user_config(authorize_items=(DEPLOY, PUSH, MERGE_TO_MAIN))

    result = answering_for(_member(deny=("deploy",)), config)

    assert [item.key for item in result.not_authorized] == [
        "deploy",
        "push",
        "merge_to_main",
    ]
    assert result.settings.reserved_terms == (
        "deploy to prod",
        "git push",
        "merge to main",
        "merge into main",
    )


def test_config_and_member_fields_reach_the_settings() -> None:
    config = user_config()

    settings = answering_for(
        _member(rules_paths=("CLAUDE.md", "docs/*.md")), config
    ).settings

    assert settings.rules_paths == ("CLAUDE.md", "docs/*.md")
    assert settings.answer_limit == config.answer_limit
    assert settings.passages_max_chars == config.passages_max_chars
    assert settings.answer_model == config.answer_model
    assert settings.check_model == config.check_model
    assert settings.max_cost_usd == config.max_cost_usd


@pytest.mark.parametrize("field", ["allow", "deny"])
def test_an_unknown_authorize_key_names_member_and_key(field: str) -> None:
    member = _member("member-7", **{field: ("retired_item",)})

    with pytest.raises(ConfigError, match=r"member-7.*retired_item"):
        answering_for(member, user_config())


def test_an_item_both_allowed_and_denied_stays_not_authorized() -> None:
    result = answering_for(
        _member(allow=("merge_to_main",), deny=("merge_to_main",)), user_config()
    )

    assert MERGE_TO_MAIN in result.not_authorized
