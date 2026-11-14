"""One member's answering settings, from its stored settings and the user config (D8).

The not-authorized items are the config items with ``denied_by_default: true`` that the
member does not allow, plus the items it denies, in config order. The same items give
both what the models are told (``not_authorized``) and what the screen matches
(``settings.reserved_terms``), so allowing an item removes it from both.
"""

from __future__ import annotations

from dataclasses import dataclass

from amoeba.answering.settings import AnswererSettings, RulesChoice
from amoeba.config.user_config import ConfigError, NotAuthorizedItem, UserConfig
from amoeba.store.models import MemberSettings
from amoeba.store.vocabulary import RulesFrom


@dataclass(frozen=True)
class MemberAnswering:
    settings: AnswererSettings
    #: The items this member's answers may not authorize, with their descriptions.
    not_authorized: tuple[NotAuthorizedItem, ...]


def _require_known_keys(member: MemberSettings, config: UserConfig) -> None:
    known = {item.key for item in config.authorize_items}
    for key in (*member.authorize_allow, *member.authorize_deny):
        if key not in known:
            raise ConfigError(
                f"member {member.project_id}: authorize key {key!r} is not in the "
                "config's authorize_items"
            )


def rules_choice(member: MemberSettings, config: UserConfig) -> RulesChoice:
    """The member's rules: its own entries, or the config's current default (D7).

    The default is read here, at answering time, so a config edit changes every
    member that is on it.
    """
    if member.rules_from is RulesFrom.CONFIG_DEFAULT:
        return RulesChoice(entries=config.default_rules_paths, optional=True)
    return RulesChoice(entries=member.rules_paths, optional=False)


def answering_for(
    member_settings: MemberSettings, config: UserConfig
) -> MemberAnswering:
    """The settings and not-authorized items for one member.

    Raises:
        ConfigError: The member refers to an authorize key the config lacks.
    """
    _require_known_keys(member_settings, config)
    allowed = set(member_settings.authorize_allow)
    denied = set(member_settings.authorize_deny)
    not_authorized = tuple(
        item
        for item in config.authorize_items
        if (item.denied_by_default and item.key not in allowed) or item.key in denied
    )
    settings = AnswererSettings(
        answer_limit=config.answer_limit,
        reserved_terms=tuple(
            phrase for item in not_authorized for phrase in item.screen_phrases
        ),
        rules=rules_choice(member_settings, config),
        passages_max_chars=config.passages_max_chars,
        answer_model=config.answer_model,
        check_model=config.check_model,
        max_cost_usd=config.max_cost_usd,
    )
    return MemberAnswering(settings=settings, not_authorized=not_authorized)
