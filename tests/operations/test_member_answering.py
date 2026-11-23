"""``answering_for``: per-member not-authorized items and the settings they feed."""

from __future__ import annotations

import pytest
from user_configs import DEPLOY, MERGE_TO_MAIN, PUSH, user_config

from amoeba.answering.settings import RulesChoice
from amoeba.config.user_config import ConfigError
from amoeba.operations.member_answering import answering_for
from amoeba.store.models import MemberSettings
from amoeba.store.vocabulary import RulesFrom


def _member(
    project_id: str = "m",
    *,
    allow: tuple[str, ...] = (),
    deny: tuple[str, ...] = (),
    rules_paths: tuple[str, ...] = ("CLAUDE.md",),
    rules_from: RulesFrom = RulesFrom.NAMED,
) -> MemberSettings:
    return MemberSettings(
        project_id=project_id,
        rules_paths=rules_paths,
        authorize_allow=allow,
        authorize_deny=deny,
        rules_from=rules_from,
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

    assert settings.rules == RulesChoice(
        entries=("CLAUDE.md", "docs/*.md"), optional=False
    )
    assert settings.answer_limit == config.answer_limit
    assert settings.passages_max_chars == config.passages_max_chars
    assert settings.answer_model == config.answer_model
    assert settings.check_model == config.check_model
    assert settings.max_cost_usd == config.max_cost_usd


def test_a_named_member_gets_its_stored_entries_as_required() -> None:
    rules = answering_for(_member(rules_paths=("docs/rules.md",)), user_config())

    assert rules.settings.rules == RulesChoice(
        entries=("docs/rules.md",), optional=False
    )


def test_a_named_member_with_no_entries_has_an_empty_required_choice() -> None:
    rules = answering_for(_member(rules_paths=()), user_config())

    assert rules.settings.rules == RulesChoice(entries=(), optional=False)


def test_a_default_member_gets_the_configs_current_entries_as_optional() -> None:
    member = _member(rules_paths=(), rules_from=RulesFrom.CONFIG_DEFAULT)

    rules = answering_for(member, user_config())

    assert rules.settings.rules == RulesChoice(
        entries=("CLAUDE.md", "AGENTS.md"), optional=True
    )


@pytest.mark.parametrize("field", ["allow", "deny"])
def test_an_unknown_authorize_key_names_member_and_key(field: str) -> None:
    retired = ("retired_item",)
    member = _member(
        "member-7",
        allow=retired if field == "allow" else (),
        deny=retired if field == "deny" else (),
    )

    with pytest.raises(ConfigError, match=r"member-7.*retired_item"):
        answering_for(member, user_config())


def test_an_item_both_allowed_and_denied_stays_not_authorized() -> None:
    result = answering_for(
        _member(allow=("merge_to_main",), deny=("merge_to_main",)), user_config()
    )

    assert MERGE_TO_MAIN in result.not_authorized
